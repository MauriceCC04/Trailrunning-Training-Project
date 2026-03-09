# src/trailtraining/llm/constraints.py
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from typing import Any, Dict, List, Optional, Tuple


@dataclass(frozen=True)
class ConstraintConfig:
    # existing
    max_ramp_pct: float = 10.0
    max_consecutive_hard: int = 2

    # ---- new quality knobs (defaults chosen to be conservative) ----
    max_hard_per_7d: int = 3
    min_rest_per_7d: int = 1
    min_signal_ids_per_day: int = 1

    # Compare weekly_totals.planned_moving_time_hours to sum(day.duration_minutes)/60
    weekly_time_tolerance_pct: float = 30.0  # allow some mismatch

    # Rest-day expectations
    rest_day_max_minutes: int = 30
    require_rest_session_type: bool = True


def _as_date(s: Any) -> Optional[date]:
    if not isinstance(s, str):
        return None
    try:
        return date.fromisoformat(s)
    except Exception:
        return None


def _v(
    code: str,
    severity: str,
    category: str,
    message: str,
    *,
    penalty: Optional[int] = None,
    details: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    # Default penalties by severity if not specified
    default_penalty = {"low": 3, "medium": 10, "high": 30}.get(severity, 10)
    return {
        "code": code,
        "severity": severity,
        "category": category,
        "penalty": int(default_penalty if penalty is None else penalty),
        "message": message,
        "details": details or {},
    }


def _chunk7(days: List[Dict[str, Any]]) -> List[List[Dict[str, Any]]]:
    # Simple index-based chunking (0..6, 7..13, ...)
    out: List[List[Dict[str, Any]]] = []
    for i in range(0, len(days), 7):
        out.append(days[i : i + 7])
    return out


def _normalize_days(plan_obj: Dict[str, Any]) -> List[Dict[str, Any]]:
    raw = (plan_obj.get("plan") or {}).get("days")
    if not isinstance(raw, list):
        return []
    days: List[Dict[str, Any]] = [d for d in raw if isinstance(d, dict)]
    # Sort by date if possible; otherwise keep order
    def key(d: Dict[str, Any]) -> Tuple[int, str]:
        dd = _as_date(d.get("date"))
        return (0, dd.isoformat()) if dd else (1, str(d.get("date") or ""))

    return sorted(days, key=key)


def _planned_week_hours(plan_obj: Dict[str, Any]) -> Optional[float]:
    wt = ((plan_obj.get("plan") or {}).get("weekly_totals") or {})
    v = wt.get("planned_moving_time_hours")
    return float(v) if isinstance(v, (int, float)) else None


def _sum_hours(days: List[Dict[str, Any]]) -> float:
    total_min = 0.0
    for d in days:
        m = d.get("duration_minutes")
        if isinstance(m, (int, float)):
            total_min += float(m)
    return total_min / 60.0


def _pct_diff(a: float, b: float) -> Optional[float]:
    # percent difference relative to b
    if b <= 0:
        return None
    return abs(a - b) / b * 100.0


def evaluate_training_plan_quality(
    plan_obj: Dict[str, Any],
    rollups: Optional[Dict[str, Any]],
    cfg: ConstraintConfig,
) -> Dict[str, Any]:
    """
    Returns a report:
      {score, grade, subscores, stats, violations}
    Uses:
      - existing safety constraints (ramp + consecutive hard) from validate_training_plan()
      - additional "quality" checks
    """
    # ---- Start with your existing violations (safety) ----
    base_violations = validate_training_plan(plan_obj, rollups, cfg)

    # Ensure they have category/penalty (in case validate_training_plan doesn't add them)
    violations: List[Dict[str, Any]] = []
    for v0 in base_violations:
        if not isinstance(v0, dict):
            continue
        code = str(v0.get("code") or "UNKNOWN")
        sev = str(v0.get("severity") or "medium")
        if "category" not in v0:
            v0["category"] = "safety"
        if "penalty" not in v0:
            v0["penalty"] = {"low": 3, "medium": 10, "high": 30}.get(sev, 10)
        violations.append(v0)

    days = _normalize_days(plan_obj)

    # ---- Stats ----
    hard_days = sum(1 for d in days if bool(d.get("is_hard_day")))
    rest_days = sum(1 for d in days if bool(d.get("is_rest_day")))
    stats = {"days": len(days), "hard_days": hard_days, "rest_days": rest_days}

    # ---- Structure checks ----

    # 1) Dates: duplicates / gaps
    seen = set()
    prev: Optional[date] = None
    for d in days:
        ds = d.get("date")
        dd = _as_date(ds)
        if not dd:
            violations.append(_v("BAD_DATE", "low", "structure", "Day has invalid/missing date", details={"date": ds}))
            continue

        if dd in seen:
            violations.append(_v("DUPLICATE_DATE", "high", "structure", "Duplicate date in plan.days", details={"date": ds}))
        seen.add(dd)

        if prev and (dd - prev).days != 1:
            violations.append(
                _v(
                    "NON_CONSECUTIVE_DATES",
                    "medium",
                    "structure",
                    "Plan dates are not consecutive (gap or reorder).",
                    details={"prev": prev.isoformat(), "curr": dd.isoformat()},
                )
            )
        prev = dd

    # 2) weekly_totals time vs sum(duration)
    planned_hours = _planned_week_hours(plan_obj)
    if planned_hours is not None and days:
        window = days[: min(7, len(days))]
        sum_hours = _sum_hours(window)
        diff = _pct_diff(planned_hours, sum_hours)
        if diff is not None and diff > cfg.weekly_time_tolerance_pct:
            violations.append(
                _v(
                    "WEEKLY_TOTALS_MISMATCH",
                    "low",
                    "structure",
                    f"weekly_totals.planned_moving_time_hours ({planned_hours:.1f}h) "
                    f"doesn't match sum(duration) ({sum_hours:.1f}h) within {cfg.weekly_time_tolerance_pct:.0f}%.",
                    details={"planned_hours": planned_hours, "sum_hours_first7": sum_hours, "pct_diff": diff},
                )
            )

    # ---- Safety/consistency checks beyond your current two ----

    # 3) Hard-days per 7d chunk
    for i, wk in enumerate(_chunk7(days)):
        h = sum(1 for d in wk if bool(d.get("is_hard_day")))
        if h > cfg.max_hard_per_7d:
            violations.append(
                _v(
                    "TOO_MANY_HARD_PER_WEEK",
                    "high",
                    "safety",
                    f"Week-chunk {i} has {h} hard days (max {cfg.max_hard_per_7d}).",
                    details={"week_index": i, "hard_days": h},
                )
            )

    # 4) Rest-days per 7d chunk
    for i, wk in enumerate(_chunk7(days)):
        r = sum(1 for d in wk if bool(d.get("is_rest_day")))
        if r < cfg.min_rest_per_7d:
            sev = "high" if r == 0 else "medium"
            violations.append(
                _v(
                    "NOT_ENOUGH_REST",
                    sev,
                    "safety",
                    f"Week-chunk {i} has {r} rest days (min {cfg.min_rest_per_7d}).",
                    details={"week_index": i, "rest_days": r},
                    penalty=35 if sev == "high" else 15,
                )
            )

    # 5) Rest day shape (duration + session_type)
    for d in days:
        if not bool(d.get("is_rest_day")):
            continue
        mins = d.get("duration_minutes")
        if isinstance(mins, (int, float)) and float(mins) > float(cfg.rest_day_max_minutes):
            violations.append(
                _v(
                    "REST_DAY_TOO_LONG",
                    "medium",
                    "structure",
                    f"Rest day exceeds {cfg.rest_day_max_minutes} minutes.",
                    details={"date": d.get("date"), "duration_minutes": mins},
                )
            )
        if cfg.require_rest_session_type:
            st = d.get("session_type")
            if isinstance(st, str) and st != "rest":
                violations.append(
                    _v(
                        "REST_DAY_BAD_SESSION_TYPE",
                        "low",
                        "structure",
                        "Rest day should have session_type == 'rest'.",
                        details={"date": d.get("date"), "session_type": st},
                    )
                )

    # ---- Justification checks ----

    # 6) signal_ids present per day
    for idx, d in enumerate(days):
        sig = d.get("signal_ids")
        n = len(sig) if isinstance(sig, list) else 0
        if n < cfg.min_signal_ids_per_day:
            violations.append(
                _v(
                    "MISSING_SIGNAL_IDS",
                    "medium",
                    "justification",
                    f"plan.days[{idx}] has empty/insufficient signal_ids (min {cfg.min_signal_ids_per_day}).",
                    details={"date": d.get("date")},
                )
            )

    # 7) citations cover used signal_ids (best-effort)
    cited = set()
    cits = plan_obj.get("citations")
    if isinstance(cits, list):
        for c in cits:
            if isinstance(c, dict) and isinstance(c.get("signal_id"), str):
                cited.add(c["signal_id"])

    used = set()
    for d in days:
        sig = d.get("signal_ids")
        if isinstance(sig, list):
            for s in sig:
                if isinstance(s, str):
                    used.add(s)

    if used and cited:
        missing = sorted(list(used - cited))
        if missing:
            violations.append(
                _v(
                    "UNCITED_SIGNAL_IDS",
                    "medium",
                    "justification",
                    "Some signal_ids used in plan.days are not present in citations[].signal_id.",
                    details={"missing_signal_ids": missing[:50], "missing_count": len(missing)},
                )
            )
    elif used and not cited:
        violations.append(
            _v(
                "MISSING_CITATIONS",
                "medium",
                "justification",
                "Plan uses signal_ids but citations[] is empty/missing.",
                details={"used_signal_ids_count": len(used)},
            )
        )

    report = score_from_violations(violations, stats=stats)
    return report


def score_from_violations(
    violations: List[Dict[str, Any]],
    *,
    stats: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    # Total score
    total_pen = 0
    by_cat: Dict[str, int] = {}
    for v in violations:
        if not isinstance(v, dict):
            continue
        pen = v.get("penalty")
        try:
            pen_i = int(pen)
        except Exception:
            pen_i = 10
        total_pen += pen_i
        cat = str(v.get("category") or "other")
        by_cat[cat] = by_cat.get(cat, 0) + pen_i

    score = max(0, 100 - total_pen)

    # Subscores: 100 - category penalty (clipped)
    subscores = {cat: max(0, 100 - pen) for cat, pen in by_cat.items()}

    # Grade
    if score >= 90:
        grade = "A"
    elif score >= 80:
        grade = "B"
    elif score >= 70:
        grade = "C"
    elif score >= 60:
        grade = "D"
    else:
        grade = "F"

    return {
        "score": score,
        "grade": grade,
        "subscores": subscores,
        "stats": stats or {},
        "violations": violations,
    }