from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Optional

from trailtraining.util.dates import _as_date
from trailtraining.util.errors import ArtifactError, MissingArtifactError
from trailtraining.util.state import load_json, save_json

log = logging.getLogger(__name__)


@dataclass(frozen=True)
class CoachPaths:
    personal_path: Path
    summary_path: Path
    rollups_path: Optional[Path]


@dataclass(frozen=True)
class CoachSourceData:
    personal: dict[str, Any]
    combined: list[dict[str, Any]]
    rollups: Optional[dict[str, Any]]


def resolve_input_paths(
    input_path: Optional[str],
    personal_path: Optional[str],
    summary_path: Optional[str],
    *,
    prompting_dir: Path,
) -> CoachPaths:
    base = Path(input_path).expanduser().resolve() if input_path else prompting_dir
    resolved_personal = (
        Path(personal_path).expanduser().resolve()
        if personal_path
        else base / "formatted_personal_data.json"
    )
    resolved_summary = (
        Path(summary_path).expanduser().resolve()
        if summary_path
        else base / "combined_summary.json"
    )
    rollups_path = base / "combined_rollups.json"
    return CoachPaths(
        personal_path=resolved_personal,
        summary_path=resolved_summary,
        rollups_path=rollups_path if rollups_path.exists() else None,
    )


def _load_required_object_artifact(path: Path, *, producer_hint: str) -> dict[str, Any]:
    raw = load_json(path, default=None)
    if raw is None:
        raise MissingArtifactError(
            message=f"Missing required artifact: {path}",
            hint=producer_hint,
        )
    if not isinstance(raw, dict):
        raise ArtifactError(
            message=f"{path.name} must be a JSON object.",
            hint=f"Got {type(raw).__name__} in {path}.",
        )
    if not raw:
        raise MissingArtifactError(
            message=f"Required artifact is empty: {path}",
            hint=producer_hint,
        )
    return raw


def _load_required_list_artifact(path: Path, *, producer_hint: str) -> list[dict[str, Any]]:
    raw = load_json(path, default=None)
    if raw is None:
        raise MissingArtifactError(
            message=f"Missing required artifact: {path}",
            hint=producer_hint,
        )
    if not isinstance(raw, list):
        raise ArtifactError(
            message=f"{path.name} must be a list of day objects.",
            hint=f"Got {type(raw).__name__} in {path}.",
        )
    if not raw:
        raise MissingArtifactError(
            message=f"Required artifact is empty: {path}",
            hint=producer_hint,
        )
    return raw


def _load_optional_rollups_artifact(path: Optional[Path]) -> Optional[dict[str, Any]]:
    if path is None:
        return None
    raw = load_json(path, default=None)
    if raw is None:
        return None
    if isinstance(raw, dict):
        return raw
    log.warning("Ignoring malformed rollups artifact at %s", path)
    return None


def dedup_activities(combined: list[dict[str, Any]]) -> list[dict[str, Any]]:
    seen: set[str] = set()
    deduped: list[dict[str, Any]] = []

    for day in combined:
        new_day = dict(day)
        activities = day.get("activities")
        if not isinstance(activities, list):
            new_day["activities"] = []
            deduped.append(new_day)
            continue

        unique: list[dict[str, Any]] = []
        for activity in activities:
            if not isinstance(activity, dict):
                continue
            activity_obj = dict(activity)
            activity_id = activity_obj.get("id")
            if activity_id is None:
                unique.append(activity_obj)
                continue

            key = str(activity_id)
            if key in seen:
                continue
            seen.add(key)
            unique.append(activity_obj)

        new_day["activities"] = unique
        deduped.append(new_day)

    return deduped


def filter_last_days(combined: list[dict[str, Any]], days: int) -> list[dict[str, Any]]:
    if not combined:
        return []
    last = _as_date(str(combined[-1].get("date", "")))
    if not last:
        return combined
    cutoff = last - timedelta(days=days - 1)
    return [
        day
        for day in combined
        if (day_date := _as_date(str(day.get("date", "")))) and day_date >= cutoff
    ]


def load_coach_source_data(
    paths: CoachPaths,
    *,
    producer_hint: str,
    days: int,
) -> CoachSourceData:
    personal = _load_required_object_artifact(paths.personal_path, producer_hint=producer_hint)
    combined_raw = _load_required_list_artifact(paths.summary_path, producer_hint=producer_hint)
    combined = filter_last_days(dedup_activities(combined_raw), days)
    rollups = _load_optional_rollups_artifact(paths.rollups_path)
    return CoachSourceData(personal=personal, combined=combined, rollups=rollups)


def load_deterministic_forecast(base_dir: Path) -> Optional[dict[str, Any]]:
    forecast_path = base_dir / "readiness_and_risk_forecast.json"
    if not forecast_path.exists():
        return None

    raw = load_json(forecast_path, default=None)
    if isinstance(raw, dict):
        return raw

    log.warning("Ignoring malformed deterministic forecast artifact at %s", forecast_path)
    return None


def build_deterministic_forecast(combined: list[dict[str, Any]]) -> Optional[dict[str, Any]]:
    try:
        from trailtraining.forecast.forecast import compute_readiness_and_risk

        forecast = compute_readiness_and_risk(combined)
    except (ImportError, AttributeError, TypeError, ValueError) as exc:
        log.warning("Deterministic forecast unavailable: %s", exc)
        return None

    return {
        "generated_at": datetime.utcnow().isoformat() + "Z",
        "result": {
            "date": forecast.date,
            "readiness": {
                "score": forecast.readiness_score,
                "status": forecast.readiness_status,
            },
            "overreach_risk": {
                "score": forecast.overreach_risk_score,
                "level": forecast.overreach_risk_level,
            },
            "inputs": forecast.inputs,
            "drivers": forecast.drivers,
        },
    }


def persist_deterministic_forecast(base_dir: Path, payload: dict[str, Any]) -> Path:
    forecast_path = base_dir / "readiness_and_risk_forecast.json"
    save_json(forecast_path, payload, compact=False)
    return forecast_path


def get_or_create_deterministic_forecast(
    base_dir: Path,
    combined: list[dict[str, Any]],
) -> Optional[dict[str, Any]]:
    loaded = load_deterministic_forecast(base_dir)
    if loaded is not None:
        return loaded

    payload = build_deterministic_forecast(combined)
    if payload is None:
        return None

    try:
        persist_deterministic_forecast(base_dir, payload)
    except Exception as exc:
        log.warning("Failed to persist deterministic forecast to %s: %s", base_dir, exc)
    return payload


def save_markdown_output(
    output_path: Optional[str],
    *,
    prompt_name: str,
    prompting_dir: Path,
    text: str,
) -> Path:
    out_path = (
        Path(output_path).expanduser().resolve()
        if output_path
        else prompting_dir / f"coach_brief_{prompt_name}.md"
    )
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(text, encoding="utf-8")
    return out_path


def save_training_plan_output(
    output_path: Optional[str],
    *,
    prompting_dir: Path,
    plan_obj: dict[str, Any],
) -> Path:
    from trailtraining.llm.shared import training_plan_to_text

    out_path = (
        Path(output_path).expanduser().resolve()
        if output_path
        else prompting_dir / "coach_brief_training-plan.json"
    )
    out_path.parent.mkdir(parents=True, exist_ok=True)
    save_json(out_path, plan_obj, compact=False)

    try:
        (out_path.parent / f"{out_path.stem}.txt").write_text(
            training_plan_to_text(plan_obj),
            encoding="utf-8",
        )
    except Exception as exc:
        log.warning("Failed to write training-plan text: %s", exc)

    return out_path
