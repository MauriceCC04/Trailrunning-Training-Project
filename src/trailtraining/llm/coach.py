from __future__ import annotations

import json
import os
import tempfile
import zipfile
from dataclasses import dataclass
from datetime import datetime, timedelta, date
from pathlib import Path
from typing import Any, Optional, Tuple, List, Dict

from openai import OpenAI

from trailtraining.llm.prompts import SYSTEM_PROMPT, PROMPTS

# If your project already has trailtraining.config with PROMPTING_DIRECTORY, this will use it.
# If not, it falls back to ./prompting
try:
    from trailtraining import config as _config  # type: ignore
    DEFAULT_PROMPTING_DIR = Path(getattr(_config, "PROMPTING_DIRECTORY"))
except Exception:
    DEFAULT_PROMPTING_DIR = Path.cwd() / "prompting"


@dataclass(frozen=True)
class CoachConfig:
    model: str = "gpt-5.2"  # GPT-5.2 Thinking in API :contentReference[oaicite:4]{index=4}
    reasoning_effort: str = "medium"  # none|low|medium|high|xhigh :contentReference[oaicite:5]{index=5}
    verbosity: str = "medium"  # low|medium|high (text.verbosity) :contentReference[oaicite:6]{index=6}
    days: int = 60
    max_chars: int = 200_000
    temperature: Optional[float] = None  # only allowed if reasoning_effort == "none" :contentReference[oaicite:7]{index=7}


def _load_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        raise FileNotFoundError(f"Missing required JSON file: {path}")
    except json.JSONDecodeError as e:
        raise ValueError(f"Failed to parse JSON: {path} ({e})")


def _parse_date(x: Any) -> Optional[date]:
    try:
        s = str(x)[:10]  # handle 'YYYY-MM-DD...' variants
        return datetime.fromisoformat(s).date()
    except Exception:
        return None


def _find_required_files(root: Path) -> Tuple[Path, Path]:
    personal = sorted(root.rglob("formatted_personal_data.json"))
    summary = sorted(root.rglob("combined_summary.json"))
    if not personal:
        raise FileNotFoundError(f"Could not find formatted_personal_data.json under: {root}")
    if not summary:
        raise FileNotFoundError(f"Could not find combined_summary.json under: {root}")
    return personal[0], summary[0]


def _dedup_activities(combined: List[Dict[str, Any]]) -> List[str]:
    notes: List[str] = []
    for day in combined:
        acts = day.get("activities")
        if not isinstance(acts, list) or not acts:
            continue

        seen = set()
        kept = []
        removed = 0

        for a in acts:
            if not isinstance(a, dict):
                continue
            key = (
                str(day.get("date", "")),
                str(a.get("start_time", "")),
                str(a.get("sport_type", "")),
                str(a.get("distance_km", "")),
                str(a.get("moving_time_sec", "")),
            )
            if key in seen:
                removed += 1
                continue
            seen.add(key)
            kept.append(a)

        if removed:
            day["activities"] = kept
            notes.append(f"{day.get('date')}: removed {removed} duplicate activities")

    return notes


def _normalize_and_slice_combined(
    combined: Any,
    days: int,
    max_chars: int,
) -> Tuple[List[Dict[str, Any]], List[str]]:
    if not isinstance(combined, list):
        raise ValueError("combined_summary.json must be a JSON array (list).")

    combined_list: List[Dict[str, Any]] = [x for x in combined if isinstance(x, dict)]
    combined_list.sort(key=lambda d: str(d.get("date", "")))  # enforce chronological

    notes: List[str] = []
    notes.extend(_dedup_activities(combined_list))

    # keep recent N days/entries
    if days and days > 0 and combined_list:
        last_d = _parse_date(combined_list[-1].get("date"))
        if last_d:
            start = last_d - timedelta(days=days - 1)
            combined_list = [
                d for d in combined_list
                if (_parse_date(d.get("date")) or last_d) >= start
            ]
        else:
            combined_list = combined_list[-days:]

    def _payload_chars(arr: List[Dict[str, Any]]) -> int:
        return len(json.dumps(arr, ensure_ascii=False, separators=(",", ":")))

    # shrink until below max_chars (keep at least ~7 entries)
    if max_chars and max_chars > 0:
        while combined_list and _payload_chars(combined_list) > max_chars and len(combined_list) > 7:
            new_len = max(7, int(len(combined_list) * 0.7))
            combined_list = combined_list[-new_len:]
            notes.append(f"Payload too large; auto-shrunk combined_summary to last {len(combined_list)} entries.")

    return combined_list, notes


def _build_user_message(
    prompt_name: str,
    personal_data: Any,
    combined_data: List[Dict[str, Any]],
    preprocessing_notes: List[str],
) -> str:
    prompt_text = PROMPTS[prompt_name].strip()
    parts: List[str] = [prompt_text, ""]

    if preprocessing_notes:
        parts.append("Data notes (preprocessing performed before this prompt):")
        parts.extend([f"- {n}" for n in preprocessing_notes])
        parts.append("")

    parts.append("Here are the JSON files for this run.\n")

    parts.append("### formatted_personal_data.json")
    parts.append("```json")
    parts.append(json.dumps(personal_data, ensure_ascii=False, separators=(",", ":")))
    parts.append("```")
    parts.append("")

    parts.append("### combined_summary.json")
    parts.append("```json")
    parts.append(json.dumps(combined_data, ensure_ascii=False, separators=(",", ":")))
    parts.append("```")

    return "\n".join(parts)


def run_coach_brief(
    prompt: str,
    cfg: CoachConfig,
    input_path: Optional[str] = None,
    personal_path: Optional[str] = None,
    summary_path: Optional[str] = None,
    output_path: Optional[str] = None,
) -> Tuple[str, Optional[str]]:
    """
    Returns (coach_text, saved_path_or_None)
    """
    if prompt not in PROMPTS:
        raise ValueError(f"Unknown prompt '{prompt}'. Choose from: {', '.join(PROMPTS.keys())}")

    # Locate files (supports directory or .zip)
    temp_dir_obj = None
    try:
        if personal_path and summary_path:
            personal_file = Path(personal_path).expanduser().resolve()
            summary_file = Path(summary_path).expanduser().resolve()
        else:
            root = DEFAULT_PROMPTING_DIR
            if input_path:
                ip = Path(input_path).expanduser().resolve()
                if ip.is_file() and ip.suffix.lower() == ".zip":
                    temp_dir_obj = tempfile.TemporaryDirectory(prefix="trailtraining_prompt_zip_")
                    with zipfile.ZipFile(ip, "r") as zf:
                        zf.extractall(temp_dir_obj.name)
                    root = Path(temp_dir_obj.name)
                else:
                    root = ip
            personal_file, summary_file = _find_required_files(root)

        personal = _load_json(personal_file)
        combined_raw = _load_json(summary_file)

        combined, prep_notes = _normalize_and_slice_combined(
            combined=combined_raw,
            days=cfg.days,
            max_chars=cfg.max_chars,
        )

        user_msg = _build_user_message(
            prompt_name=prompt,
            personal_data=personal,
            combined_data=combined,
            preprocessing_notes=prep_notes,
        )

        # ---- OpenAI call (Responses API, recommended for reasoning models) :contentReference[oaicite:8]{index=8}
        client = OpenAI()

        create_kwargs: Dict[str, Any] = {
            "model": cfg.model,
            "instructions": SYSTEM_PROMPT,
            "input": [{"role": "user", "content": user_msg}],
            "reasoning": {"effort": cfg.reasoning_effort},
            "text": {"verbosity": cfg.verbosity},
        }

        # temperature only allowed when reasoning.effort == "none" :contentReference[oaicite:9]{index=9}
        if cfg.reasoning_effort == "none" and cfg.temperature is not None:
            create_kwargs["temperature"] = cfg.temperature

        resp = client.responses.create(**create_kwargs)
        text = (resp.output_text or "").strip()

        # Write output
        if output_path is None:
            out = DEFAULT_PROMPTING_DIR / f"coach_brief_{prompt}.md"
        else:
            out = Path(output_path).expanduser().resolve()

        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(text + "\n", encoding="utf-8")
        return text, str(out)

    finally:
        if temp_dir_obj is not None:
            temp_dir_obj.cleanup()
