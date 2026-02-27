# src/trailtraining/pipelines/intervals.py
from __future__ import annotations

import json
import os
from datetime import date, timedelta
from typing import Any, Dict, List, Optional

import requests

from trailtraining import config

BASE_URL = os.getenv("INTERVALS_BASE_URL", "https://intervals.icu/api/v1")


def _get_env(name: str, required: bool = True, default: Optional[str] = None) -> str:
    v = os.getenv(name, default) or ""
    v = v.strip()
    if required and not v:
        raise RuntimeError(f"Missing environment variable: {name}")
    return v


def _pick(obj: Dict[str, Any], *keys: str, default: Any = None) -> Any:
    for k in keys:
        if k in obj and obj[k] is not None:
            return obj[k]
    return default


def _to_int(v: Any, default: int = -1) -> int:
    if v is None:
        return default
    try:
        return int(float(v))
    except Exception:
        return default


def _auth_headers() -> Dict[str, str]:
    # If you ever add OAuth later:
    bearer = os.getenv("INTERVALS_ACCESS_TOKEN", "").strip()
    if bearer:
        return {"Authorization": f"Bearer {bearer}"}

    # API key (personal use): Basic auth where username is literally "API_KEY"
    api_key = (os.getenv("INTERVALS_API_KEY") or getattr(config, "INTERVALS_API_KEY", "")).strip()
    if not api_key:
        raise RuntimeError("Missing INTERVALS_API_KEY (or INTERVALS_ACCESS_TOKEN).")

    import base64
    basic = base64.b64encode(f"API_KEY:{api_key}".encode("utf-8")).decode("ascii")
    return {"Authorization": f"Basic {basic}"}


def fetch_wellness(oldest: str, newest: str) -> List[Dict[str, Any]]:
    athlete_id = (os.getenv("INTERVALS_ATHLETE_ID") or getattr(config, "INTERVALS_ATHLETE_ID", "0")).strip() or "0"
    url = f"{BASE_URL}/athlete/{athlete_id}/wellness"
    params = {"oldest": oldest, "newest": newest}

    resp = requests.get(url, params=params, headers={**_auth_headers(), "Accept": "application/json"}, timeout=30)
    resp.raise_for_status()
    data = resp.json()
    if not isinstance(data, list):
        raise ValueError(f"Unexpected Intervals wellness response (expected list). Got: {type(data)}")
    return data


def normalize_to_filtered_sleep(entry: Dict[str, Any]) -> Dict[str, Any]:
    # Date key: Intervals often uses `id` for the day (YYYY-MM-DD)
    day = str(_pick(entry, "id", "day", "date", "calendarDate", default=""))[:10]
    if not day:
        raise ValueError(f"Wellness entry missing date/id: {entry}")

    sleep_secs = _to_int(_pick(entry, "sleepSecs", "sleep_seconds", "sleepTimeSeconds"))
    resting_hr = _to_int(_pick(entry, "restingHR", "restingHr", "restingHeartRate"))

    # Sleep stages may or may not exist in Intervals for your source; keep defaults if missing
    deep = _to_int(_pick(entry, "deepSleepSecs", "deepSleepSeconds"))
    light = _to_int(_pick(entry, "lightSleepSecs", "lightSleepSeconds"))
    rem = _to_int(_pick(entry, "remSleepSecs", "remSleepSeconds"))
    awake = _to_int(_pick(entry, "awakeSleepSecs", "awakeSleepSeconds"))

    # HRV/status/body battery are Garmin-ish fields expected by your current schema
    avg_hrv = _to_int(_pick(entry, "avgOvernightHrv", "hrv", "hrvRmssd", "rmssd"))
    hrv_status = str(_pick(entry, "hrvStatus", "hrv_status", default="") or "")
    body_battery_change = _to_int(_pick(entry, "bodyBatteryChange", "body_battery_change"))

    return {
        "calendarDate": day,
        "sleepTimeSeconds": sleep_secs,
        "restingHeartRate": resting_hr,
        "avgOvernightHrv": avg_hrv,
    }

def ensure_personal_stub() -> None:
    # coach requires this file to exist :contentReference[oaicite:2]{index=2}
    out_path = os.path.join(config.PROMPTING_DIRECTORY, "formatted_personal_data.json")
    if os.path.exists(out_path):
        return
    stub = {"userInfo": {}, "biometricProfile": {}}
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(stub, f, indent=2)


def main() -> None:
    os.makedirs(config.PROCESSING_DIRECTORY, exist_ok=True)
    os.makedirs(config.PROMPTING_DIRECTORY, exist_ok=True)

    newest = os.getenv("TRAILTRAINING_WELLNESS_NEWEST", date.today().isoformat())
    lookback_days = int(os.getenv("TRAILTRAINING_WELLNESS_LOOKBACK_DAYS", "200"))
    oldest = os.getenv("TRAILTRAINING_WELLNESS_OLDEST", (date.today() - timedelta(days=lookback_days)).isoformat())

    print(f"Fetching Intervals wellness {oldest} → {newest} ...")
    raw = fetch_wellness(oldest=oldest, newest=newest)
    normalized = [normalize_to_filtered_sleep(x) for x in raw]
    normalized.sort(key=lambda r: r["calendarDate"])

    out = os.path.join(config.PROCESSING_DIRECTORY, "filtered_sleep.json")
    with open(out, "w", encoding="utf-8") as f:
        json.dump(normalized, f, indent=4)

    ensure_personal_stub()
    print(f"Intervals wellness saved: {out}")