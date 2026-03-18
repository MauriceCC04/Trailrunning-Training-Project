from __future__ import annotations

import json
import logging
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Optional

from openai import OpenAI

import trailtraining.llm.coach_prompting as _coach_prompting
from trailtraining import config
from trailtraining.llm.coach_io import (
    get_or_create_deterministic_forecast,
    load_coach_source_data,
    resolve_input_paths,
    save_markdown_output,
    save_training_plan_output,
)
from trailtraining.llm.guardrails import apply_eval_coach_guardrails
from trailtraining.llm.presets import get_system_prompt
from trailtraining.llm.rubrics import default_primary_goal_for_style
from trailtraining.llm.schemas import TRAINING_PLAN_SCHEMA, ensure_training_plan_shape
from trailtraining.llm.shared import apply_primary_goal as _apply_primary_goal
from trailtraining.llm.shared import call_with_param_fallback as _call_with_param_fallback
from trailtraining.llm.shared import call_with_schema as _call_with_schema
from trailtraining.llm.shared import extract_json_object as _extract_json_object
from trailtraining.llm.shared import make_openrouter_client as _make_openrouter_client
from trailtraining.llm.shared import recompute_planned_hours as _recompute_planned_hours
from trailtraining.util.errors import MissingArtifactError
from trailtraining.util.state import _json_default

log = logging.getLogger(__name__)


def _as_dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _as_list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def _as_str(value: Any) -> str:
    return value.strip() if isinstance(value, str) else ""


def _lifestyle_notes_section(lifestyle_notes: str) -> list[str]:
    return _coach_prompting._lifestyle_notes_section(lifestyle_notes)


def _build_prompt_text(
    prompt_name: str,
    personal: dict[str, Any],
    rollups: Optional[dict[str, Any]],
    combined: list[dict[str, Any]],
    deterministic_forecast: Optional[dict[str, Any]],
    *,
    style: str,
    primary_goal: str,
    lifestyle_notes: str,
    max_chars: int,
    detail_days: int,
    plan_days: int = 7,
) -> str:
    return _coach_prompting.build_prompt_text(
        prompt_name=prompt_name,
        personal=personal,
        rollups=rollups,
        combined=combined,
        deterministic_forecast=deterministic_forecast,
        style=style,
        primary_goal=primary_goal,
        lifestyle_notes=lifestyle_notes,
        max_chars=max_chars,
        detail_days=detail_days,
        plan_days=plan_days,
    )


@dataclass(frozen=True)
class CoachConfig:
    model: str = "openai/gpt-4o"
    reasoning_effort: str = "medium"
    verbosity: str = "medium"
    days: int = 60
    max_chars: int = 200_000
    temperature: Optional[float] = None
    style: str = "trailrunning"
    primary_goal: str = ""
    plan_days: int = 7
    lifestyle_notes: str = ""

    @classmethod
    def from_env(cls) -> CoachConfig:
        def _env_int(name: str, default: int) -> int:
            value = os.getenv(name)
            try:
                return int(value) if value and value.strip() else default
            except ValueError:
                return default

        style = os.getenv("TRAILTRAINING_COACH_STYLE", cls.style)
        primary_goal = os.getenv("TRAILTRAINING_PRIMARY_GOAL") or default_primary_goal_for_style(
            style
        )
        lifestyle_notes = os.getenv("TRAILTRAINING_LIFESTYLE_NOTES", "").strip()
        return cls(
            model=os.getenv("TRAILTRAINING_LLM_MODEL", cls.model),
            reasoning_effort=os.getenv("TRAILTRAINING_REASONING_EFFORT", cls.reasoning_effort),
            verbosity=os.getenv("TRAILTRAINING_VERBOSITY", cls.verbosity),
            days=_env_int("TRAILTRAINING_COACH_DAYS", cls.days),
            max_chars=_env_int("TRAILTRAINING_COACH_MAX_CHARS", cls.max_chars),
            style=style,
            primary_goal=primary_goal,
            plan_days=_env_int("TRAILTRAINING_PLAN_DAYS", cls.plan_days),
            lifestyle_notes=lifestyle_notes,
        )


def _apply_lifestyle_notes(plan_obj: dict[str, Any], lifestyle_notes: str) -> None:
    notes = lifestyle_notes.strip() if isinstance(lifestyle_notes, str) else ""
    meta = _as_dict(plan_obj.get("meta"))
    if meta:
        meta["lifestyle_notes"] = notes
        plan_obj["meta"] = meta


def _apply_deterministic_readiness(
    plan_obj: dict[str, Any],
    det_forecast: Optional[dict[str, Any]],
) -> None:
    if not isinstance(det_forecast, dict):
        return

    result = _as_dict(det_forecast.get("result"))
    readiness = _as_dict(result.get("readiness"))
    status = readiness.get("status")
    if status not in ("primed", "steady", "fatigued"):
        return

    plan_readiness = _as_dict(plan_obj.get("readiness"))
    if not plan_readiness:
        return

    score = readiness.get("score")
    prefix = (
        f"Deterministic readiness: {status} (score {score})."
        if isinstance(score, (int, float))
        else f"Deterministic readiness: {status}."
    )
    old_rationale = _as_str(plan_readiness.get("rationale"))
    plan_readiness["status"] = status
    plan_readiness["rationale"] = (
        f"{prefix} {old_rationale}"
        if old_rationale and not old_rationale.lower().startswith("deterministic")
        else prefix
    )
    plan_obj["readiness"] = plan_readiness

    data_notes = _as_list(plan_obj.get("data_notes"))
    note = "Readiness status was set from deterministic readiness_and_risk_forecast.json."
    if note not in data_notes:
        data_notes.append(note)
    plan_obj["data_notes"] = data_notes


def _parse_training_plan(
    out_text: str,
    client: OpenAI,
    cfg: CoachConfig,
    system_instructions: str,
) -> dict[str, Any]:
    try:
        obj = ensure_training_plan_shape(json.loads(_extract_json_object(out_text)))
        _recompute_planned_hours(obj)
        return obj
    except Exception as exc:
        log.warning("Training-plan JSON parse/shape failed; attempting repair: %s", exc)

    repair_resp = _call_with_param_fallback(
        client,
        {
            "model": cfg.model,
            "instructions": system_instructions,
            "input": (
                f"Return ONLY valid JSON matching this schema:\n{TRAINING_PLAN_SCHEMA.get('schema')}\n\n"
                f"Your previous output was invalid. Fix it:\n{out_text}\n"
            ),
            "reasoning": {"effort": "none"},
            "text": {"verbosity": "low"},
        },
    )
    repaired = getattr(repair_resp, "output_text", None) or str(repair_resp)
    obj = ensure_training_plan_shape(json.loads(_extract_json_object(repaired)))
    _recompute_planned_hours(obj)
    return obj


def _run_training_plan(
    client: OpenAI,
    api_kwargs: dict[str, Any],
    cfg: CoachConfig,
    resolved_goal: str,
    deterministic_forecast: Optional[dict[str, Any]],
    rollups: Optional[dict[str, Any]],
    output_path: Optional[str],
    *,
    prompting_dir: Path,
) -> tuple[str, str]:
    system_instructions = str(api_kwargs.get("instructions") or "")
    resp = _call_with_schema(client, api_kwargs, TRAINING_PLAN_SCHEMA)
    out_text = getattr(resp, "output_text", None) or str(resp)

    obj = _parse_training_plan(out_text, client, cfg, system_instructions)
    _apply_primary_goal(obj, resolved_goal)
    _apply_lifestyle_notes(obj, cfg.lifestyle_notes)
    _apply_deterministic_readiness(obj, deterministic_forecast)
    apply_eval_coach_guardrails(obj, rollups)

    out_path = save_training_plan_output(
        output_path,
        prompting_dir=prompting_dir,
        plan_obj=obj,
    )
    return json.dumps(obj, indent=2, ensure_ascii=False, default=_json_default), str(out_path)


def run_coach_brief(
    *,
    prompt: str,
    cfg: CoachConfig,
    input_path: Optional[str] = None,
    personal_path: Optional[str] = None,
    summary_path: Optional[str] = None,
    output_path: Optional[str] = None,
    runtime: Optional[config.RuntimeConfig] = None,
) -> tuple[str, Optional[str]]:
    runtime = runtime or config.current()
    config.ensure_directories(runtime)
    paths = runtime.paths

    producer_hint = (
        "Run `trailtraining combine` (or `trailtraining run-all`) to generate the required inputs."
    )
    coach_paths = resolve_input_paths(
        input_path,
        personal_path,
        summary_path,
        prompting_dir=paths.prompting_directory,
    )
    source_data = load_coach_source_data(coach_paths, producer_hint=producer_hint, days=cfg.days)

    if not source_data.combined:
        raise MissingArtifactError(
            message=(
                f"{coach_paths.summary_path.name} contains no usable day objects in the last {cfg.days} days."
            ),
            hint="Fetch fresh source data and rerun `trailtraining combine`.",
        )

    deterministic_forecast = get_or_create_deterministic_forecast(
        coach_paths.summary_path.parent,
        source_data.combined,
    )
    detail_days = max(
        1,
        min(
            int(os.getenv("TRAILTRAINING_COACH_DETAIL_DAYS", "14")),
            len(source_data.combined),
        ),
    )
    resolved_goal = (cfg.primary_goal or "").strip() or default_primary_goal_for_style(cfg.style)

    prompt_text = _build_prompt_text(
        prompt_name=prompt,
        personal=source_data.personal,
        rollups=source_data.rollups,
        combined=source_data.combined,
        deterministic_forecast=deterministic_forecast,
        style=cfg.style,
        primary_goal=resolved_goal,
        lifestyle_notes=cfg.lifestyle_notes,
        max_chars=cfg.max_chars,
        detail_days=detail_days,
        plan_days=cfg.plan_days,
    )

    client = _make_openrouter_client()
    api_kwargs: dict[str, Any] = {
        "model": cfg.model,
        "instructions": get_system_prompt(cfg.style),
        "input": prompt_text,
        "reasoning": {"effort": cfg.reasoning_effort},
        "text": {"verbosity": cfg.verbosity},
    }
    if cfg.reasoning_effort == "none" and cfg.temperature is not None:
        api_kwargs["temperature"] = cfg.temperature

    if prompt == "training-plan":
        return _run_training_plan(
            client,
            api_kwargs,
            cfg,
            resolved_goal,
            deterministic_forecast,
            source_data.rollups,
            output_path,
            prompting_dir=paths.prompting_directory,
        )

    resp = _call_with_param_fallback(client, api_kwargs)
    out_text = getattr(resp, "output_text", None) or str(resp)
    out_path = save_markdown_output(
        output_path,
        prompt_name=prompt,
        prompting_dir=paths.prompting_directory,
        text=out_text,
    )
    return out_text, str(out_path)
