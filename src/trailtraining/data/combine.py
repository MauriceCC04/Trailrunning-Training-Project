# pipelines/combine_jsons.py

from trailtraining.pipelines import garmin as garmin_pipeline, download_garmin_data, strava as strava_pipeline
import os
from trailtraining import config
import json
import re
from datetime import datetime

def duration_to_seconds(duration_str):
    pattern = r"P(?:(\d+)D)?T(?:(\d+)H)?(?:(\d+)M)?(?:(\d+)S)?"
    match = re.match(pattern, duration_str.replace("P0D", "P"))
    if not match:
        return 0
    days, hours, minutes, seconds = [int(x) if x else 0 for x in match.groups()]
    return days * 86400 + hours * 3600 + minutes * 60 + seconds

def parse_garmin_entry(entry):
    return {
        "date": entry["calendarDate"],
        "sleep_hours": round(entry["sleepTimeSeconds"] / 3600, 2),
        "resting_hr": entry["restingHeartRate"],
        "avg_hrv": entry["avgOvernightHrv"],
        "hrv_status": entry["hrvStatus"],
        "body_battery_change": entry["bodyBatteryChange"],
        "sleep_time_seconds": entry["sleepTimeSeconds"],
        "deep_sleep_seconds": entry["deepSleepSeconds"],
        "light_sleep_seconds": entry["lightSleepSeconds"],
        "rem_sleep_seconds": entry["remSleepSeconds"],
        "awake_seconds": entry["awakeSleepSeconds"],
    }


def parse_sleep_entry(entry):
    # only keep what you want
    sleep_seconds = entry.get("sleepTimeSeconds")
    return {
        "date": entry["calendarDate"],
        "sleep_hours": round((sleep_seconds or 0) / 3600, 2),
        "sleep_time_seconds": sleep_seconds,
        "resting_hr": entry.get("restingHeartRate"),
        "avg_hrv": entry.get("avgOvernightHrv"),
    }

def _date_only_from_strava(dt):
    s = str(dt).replace('Z','')
    if '.' in s:
        s = s.split('.')[0]
    if 'T' not in s:
        s = s.replace(' ', 'T')
    return datetime.fromisoformat(s).date().isoformat()
import math, re

def _to_float(v, default=0.0):
    if v is None:
        return default
    if isinstance(v, (int, float)):
        return float(v)
    token = str(v).strip().split()[0]
    try:
        return float(token)
    except Exception:
        return default

def _duration_to_seconds(x):
    if x is None:
        return 0
    if isinstance(x, (int, float)):
        return int(x)
    s = str(x).strip()
    m = re.match(r'(?:(\d+)\s+days?\s+)?(\d{1,2}):(\d{2}):(\d{2})', s)
    if m:
        days = int(m.group(1) or 0); h, m_, sec = map(int, m.groups()[-3:])
        return days*86400 + h*3600 + m_*60 + sec
    if s.startswith("P"):
        m = re.match(r"P(?:(\d+)D)?T(?:(\d+)H)?(?:(\d+)M)?(?:(\d+)S)?", s.replace("P0D","P"))
        if m:
            d,h,mi,se = [int(x) if x else 0 for x in m.groups()]
            return d*86400 + h*3600 + mi*60 + se
    try:
        return int(float(s))
    except Exception:
        return 0
def safe_round(value, ndigits=1, default=None):
    if value is None:
        return default
    try:
        return round(float(value), ndigits)
    except (ValueError, TypeError):
        return default

def parse_strava_entry(entry):
    # normalize datetime safely (can be datetime-like or string)
    dt_raw = entry.get("start_date_local")
    dt_str = str(dt_raw).replace("T", " ")
    date_str = dt_str[:10]  # "YYYY-MM-DD"

    distance_m = _to_float(entry.get("distance"), default=0.0)  # Strava distance is meters
    elev_gain_m = _to_float(entry.get("total_elevation_gain"), default=0.0)

    return {
        "date": date_str,
        "start_time": dt_str,
        "sport_type": entry.get("sport_type"),
        "activity_name": entry.get("name"),
        "activity": entry.get("activity"),
        "distance_km": round(distance_m / 1000.0, 2),
        "avg_hr": safe_round(entry.get("average_heartrate"), 1),
        "max_hr": safe_round(entry.get("max_heartrate"), 1),
        "elevation_gain_m": elev_gain_m,
        "elev_low": entry.get("elev_low"),
        "elev_high": entry.get("elev_high"),
        "moving_time_sec": _duration_to_seconds(entry.get("moving_time")),
        "elapsed_time_sec": _duration_to_seconds(entry.get("elapsed_time")),
    }

def main():
    with open(os.path.join(config.PROCESSING_DIRECTORY, "filtered_sleep.json")) as f:
        sleep_data = json.load(f)

    with open(os.path.join(config.PROCESSING_DIRECTORY, "strava_activities.json")) as f:
        strava_data = json.load(f)

    parsed_sleep = {e["calendarDate"]: parse_sleep_entry(e) for e in sleep_data}

    parsed_strava = {}
    for entry in strava_data:
        date_key = str(entry.get("start_date_local")).replace("T", " ")[:10]
        parsed_strava.setdefault(date_key, []).append(parse_strava_entry(entry))

    # union of dates so days with activities but no sleep still appear
    all_dates = sorted(set(parsed_sleep.keys()) | set(parsed_strava.keys()))

    combined_summary = []
    for d in all_dates:
        summary = {"date": d}
        if d in parsed_sleep:
            # parsed_sleep[d] already contains "date", but we don’t need duplicates
            sleep_fields = dict(parsed_sleep[d])
            sleep_fields.pop("date", None)
            summary.update(sleep_fields)

        summary["activities"] = parsed_strava.get(d, [])
        combined_summary.append(summary)

    output_file = os.path.join(config.PROMPTING_DIRECTORY, "combined_summary.json")
    if os.path.exists(output_file):
        os.remove(output_file)

    with open(output_file, "w") as f:
        json.dump(combined_summary, f, indent=4)


if __name__ == "__main__":
    main()
