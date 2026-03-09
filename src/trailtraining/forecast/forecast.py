# src/trailtraining/forecast/forecast.py
from __future__ import annotations

import math
import os
from dataclasses import dataclass
from datetime import date, timedelta
from typing import Any, Dict, List, Optional, Sequence, Tuple

from trailtraining import config
from trailtraining.util.state import load_json, save_json


# ----------------------------
# Small helpers (no deps)
# ----------------------------
def _as_date(s: Any) -> Optional[date]:
    if not isinstance(s, str) or len(s) < 10:
        return None
    try:
        return date.fromisoformat(s[:10])
    except Exception:
        return None


def _mean(xs: Sequence[float]) -> Optional[float]:
    xs2 = [float(x) for x in xs if x is not None]
    if not xs2:
        return None
    return sum(xs2) / len(xs2)


def _std(xs: Sequence[float]) -> Optional[float]:
    xs2 = [float(x) for x in xs if x is not None]
    if len(xs2) < 2:
        return None
    m = sum(xs2) / len(xs2)
    v = sum((x - m) ** 2 for x in xs2) / (len(xs2) - 1)
    return math.sqrt(v) if v > 0 else 0.0


def _z(x: Optional[float], mu: Optional[float], sig: Optional[float]) -> float:
    if x is None or mu is None or sig is None or sig == 0:
        return 0.0
    return (x - mu) / sig


def _quantile(xs: List[float], q: float) -> Optional[float]:
    ys = sorted(float(x) for x in xs if x is not None)
    if not ys:
        return None
    q = max(0.0, min(1.0, q))
    i = int(round((len(ys) - 1) * q))
    return ys[i]


# ----------------------------
# Parse day -> metrics you have today
# ----------------------------
def _sleep_hours(day_obj: Dict[str, Any]) -> Optional[float]:
    sleep = day_obj.get("sleep")
    if not isinstance(sleep, dict):
        return None
    secs = sleep.get("sleepTimeSeconds")
    if isinstance(secs, (int, float)) and secs > 0:
        return float(secs) / 3600.0
    return None


def _sleep_int(day_obj: Dict[str, Any], key: str) -> Optional[float]:
    sleep = day_obj.get("sleep")
    if not isinstance(sleep, dict):
        return None
    v = sleep.get(key)
    # Treat -1 as missing (matches your existing conventions)
    if isinstance(v, (int, float)) and int(v) != -1:
        return float(v)
    return None


def _day_load(day_obj: Dict[str, Any]) -> Dict[str, float]:
    acts = day_obj.get("activities") or []
    if not isinstance(acts, list):
        acts = []

    dist_m = 0.0
    mv_s = 0.0
    elev_m = 0.0
    hr_sum = 0.0
    hr_n = 0
    ip_sum = 0.0
    ip_n = 0

    for a in acts:
        if not isinstance(a, dict):
            continue
        d = a.get("distance")
        if isinstance(d, (int, float)):
            dist_m += float(d)

        mv = a.get("moving_time")
        if isinstance(mv, (int, float)):
            mv_s += float(mv)

        el = a.get("total_elevation_gain")
        if isinstance(el, (int, float)):
            elev_m += float(el)

        hr = a.get("average_heartrate")
        if isinstance(hr, (int, float)):
            hr_sum += float(hr)
            hr_n += 1

        mx = a.get("max_heartrate")
        if isinstance(hr, (int, float)) and isinstance(mx, (int, float)) and mx > 0:
            ip_sum += float(hr) / float(mx)
            ip_n += 1

    return {
        "distance_km": dist_m / 1000.0,
        "moving_time_h": mv_s / 3600.0,
        "elevation_m": elev_m,
        "activity_count": float(len(acts)),
        "avg_hr_mean": (hr_sum / hr_n) if hr_n else 0.0,
        "intensity_proxy": (ip_sum / ip_n) if ip_n else 0.0,
    }


def _roll(rows: List[Dict[str, Any]], i: int, days: int) -> List[Dict[str, Any]]:
    # trailing window INCLUDING row i
    start = max(0, i - days + 1)
    return rows[start : i + 1]


def _roll_prev(rows: List[Dict[str, Any]], i: int, days: int) -> List[Dict[str, Any]]:
    # trailing window EXCLUDING row i (useful to avoid leakage for some baselines)
    end = max(0, i)
    start = max(0, end - days)
    return rows[start:end]


def _sum_field(win: List[Dict[str, Any]], key: str) -> float:
    s = 0.0
    for r in win:
        v = r.get(key)
        if isinstance(v, (int, float)):
            s += float(v)
    return s


def _mean_field(win: List[Dict[str, Any]], key: str) -> Optional[float]:
    xs = []
    for r in win:
        v = r.get(key)
        if isinstance(v, (int, float)):
            xs.append(float(v))
    return _mean(xs)


def _std_field(win: List[Dict[str, Any]], key: str) -> Optional[float]:
    xs = []
    for r in win:
        v = r.get(key)
        if isinstance(v, (int, float)):
            xs.append(float(v))
    return _std(xs)


# ----------------------------
# Proxy readiness + proxy risk inputs
# ----------------------------
def build_daily_rows(combined: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []
    for d in combined:
        if not isinstance(d, dict):
            continue
        dd = _as_date(d.get("date"))
        if not dd:
            continue

        sleep = d.get("sleep") if isinstance(d.get("sleep"), dict) else {}
        def sget(k: str) -> Optional[float]:
            v = sleep.get(k)
            if isinstance(v, (int, float)) and float(v) != -1:
                return float(v)
            return None

        sleep_s = sget("sleepTimeSeconds")
        deep_s = sget("deepSleepSeconds")
        rem_s  = sget("remSleepSeconds")
        awake_s = sget("awakeSleepSeconds")

        sleep_h = (sleep_s / 3600.0) if sleep_s and sleep_s > 0 else None
        awake_h = (awake_s / 3600.0) if awake_s and awake_s > 0 else 0.0  # treat missing as 0

        deep_frac = (deep_s / sleep_s) if (deep_s and sleep_s and sleep_s > 0) else 0.0
        rem_frac  = (rem_s  / sleep_s) if (rem_s  and sleep_s and sleep_s > 0) else 0.0

        load = _day_load(d)

        row = {
            "date": dd.isoformat(),
            "sleep_h": sleep_h,
            "awake_h": awake_h,
            "deep_frac": float(deep_frac),
            "rem_frac": float(rem_frac),
            "body_battery": sget("bodyBatteryChange"),
            "rhr": sget("restingHeartRate"),
            "restless": sget("restlessMomentsCount"),
            **load,
        }
        rows.append(row)

    rows.sort(key=lambda r: r["date"])
    return rows


def compute_proxy_readiness(rows: List[Dict[str, Any]]) -> List[Optional[float]]:
    """
    Proxy readiness score in [0, 100], HRV-free version for your dataset.
    Higher is better.
    """
    out: List[Optional[float]] = [None] * len(rows)
    for i in range(len(rows)):
        b28 = _roll_prev(rows, i, 28)

        sh = rows[i].get("sleep_h")
        bb = rows[i].get("body_battery")
        rhr = rows[i].get("rhr")
        awake = rows[i].get("awake_h")
        deepf = rows[i].get("deep_frac")
        remf  = rows[i].get("rem_frac")

        z_sleep = _z(sh, _mean_field(b28, "sleep_h"), _std_field(b28, "sleep_h"))
        z_bb    = _z(bb, _mean_field(b28, "body_battery"), _std_field(b28, "body_battery"))
        z_rhr   = _z(rhr, _mean_field(b28, "rhr"), _std_field(b28, "rhr"))
        z_awake = _z(awake, _mean_field(b28, "awake_h"), _std_field(b28, "awake_h"))

        # load ratio (acute 7d vs chronic 28d)
        w7 = _roll(rows, i, 7)
        w28 = _roll(rows, i, 28)
        acute7 = _sum_field(w7, "moving_time_h")
        chronic28 = _sum_field(w28, "moving_time_h")
        chronic7_equiv = (chronic28 / 4.0) if chronic28 > 0 else None
        load_ratio = (acute7 / chronic7_equiv) if (chronic7_equiv and chronic7_equiv > 0) else 1.0

        # normalize load ratio relative to recent history
        lr_hist = []
        for j in range(max(0, i - 120), i):
            w7j = _roll(rows, j, 7)
            w28j = _roll(rows, j, 28)
            a7 = _sum_field(w7j, "moving_time_h")
            c28 = _sum_field(w28j, "moving_time_h")
            c7 = (c28 / 4.0) if c28 > 0 else None
            if c7 and c7 > 0:
                lr_hist.append(a7 / c7)

        z_load = _z(load_ratio, _mean(lr_hist) if lr_hist else 1.0, _std(lr_hist) if lr_hist else 0.0)

        # sleep quality proxy: deep+rem fraction (light is "whatever's left")
        sleep_quality = 0.5 * deepf + 0.5 * remf  # in [0,1] usually

        recovery = (0.55 * z_sleep) + (0.45 * z_bb) - (0.35 * z_rhr) - (0.20 * z_awake) + (6.0 * (sleep_quality - 0.35))
        readiness = 50.0 + 12.0 * (recovery - 0.65 * z_load)

        out[i] = max(0.0, min(100.0, float(readiness)))
    return out


def compute_proxy_risk_score(rows: List[Dict[str, Any]]) -> List[float]:
    """
    Overreach risk score (higher=riskier), HRV-free version:
      - high load ratio
      - sleep drop
      - body battery recovery drop
      - resting HR rise
      - awake time increase
    """
    scores: List[float] = []
    for i in range(len(rows)):
        w7 = _roll(rows, i, 7)
        w28 = _roll(rows, i, 28)

        acute7 = _sum_field(w7, "moving_time_h")
        chronic28 = _sum_field(w28, "moving_time_h")
        chronic7_equiv = (chronic28 / 4.0) if chronic28 > 0 else None
        load_ratio = (acute7 / chronic7_equiv) if (chronic7_equiv and chronic7_equiv > 0) else 1.0

        sleep7 = _mean_field(w7, "sleep_h")
        sleep28 = _mean_field(w28, "sleep_h")
        bb7 = _mean_field(w7, "body_battery")
        bb28 = _mean_field(w28, "body_battery")
        rhr7 = _mean_field(w7, "rhr")
        rhr28 = _mean_field(w28, "rhr")
        awake7 = _mean_field(w7, "awake_h")
        awake28 = _mean_field(w28, "awake_h")

        sleep_drop = ((sleep28 - sleep7) / sleep28) if (sleep7 is not None and sleep28 and sleep28 > 0) else 0.0
        bb_drop    = ((bb28 - bb7) / bb28) if (bb7 is not None and bb28 and bb28 > 0) else 0.0
        rhr_rise   = ((rhr7 - rhr28) / rhr28) if (rhr7 is not None and rhr28 and rhr28 > 0) else 0.0
        awake_rise = ((awake7 - awake28) / awake28) if (awake7 is not None and awake28 and awake28 > 0) else 0.0

        score = (
            1.25 * (load_ratio - 1.0)
            + 1.00 * max(0.0, sleep_drop)
            + 0.85 * max(0.0, bb_drop)
            + 1.10 * max(0.0, rhr_rise)
            + 0.60 * max(0.0, awake_rise)
        )
        scores.append(float(score))
    return scores

def compute_proxy_risk_score(rows: List[Dict[str, Any]]) -> List[float]:
    """
    Proxy overreach risk score (higher = riskier) from:
      - sustained high load
      - poor sleep vs baseline
      - HRV drop vs baseline
    """
    scores: List[float] = []
    for i in range(len(rows)):
        w7 = _roll(rows, i, 7)
        w28 = _roll(rows, i, 28)

        acute7 = _sum_field(w7, "moving_time_h")
        chronic28 = _sum_field(w28, "moving_time_h")
        chronic7_equiv = (chronic28 / 4.0) if chronic28 > 0 else None
        load_ratio = (acute7 / chronic7_equiv) if (chronic7_equiv and chronic7_equiv > 0) else 1.0

        sleep7 = _mean_field(w7, "sleep_h")
        sleep28 = _mean_field(w28, "sleep_h")
        hrv7 = _mean_field(w7, "hrv")
        hrv28 = _mean_field(w28, "hrv")

        sleep_drop = 0.0
        if sleep7 is not None and sleep28 is not None and sleep28 > 0:
            sleep_drop = (sleep28 - sleep7) / sleep28  # 0.10 = 10% below baseline

        hrv_drop = 0.0
        if hrv7 is not None and hrv28 is not None and hrv28 > 0:
            hrv_drop = (hrv28 - hrv7) / hrv28

        # Simple combined score (no fixed thresholds; we threshold via quantiles later)
        score = 1.2 * (load_ratio - 1.0) + 1.0 * sleep_drop + 1.0 * hrv_drop
        scores.append(float(score))
    return scores


# ----------------------------
# Minimal ML (SGD linear / logistic)
# ----------------------------
@dataclass
class Scaler:
    mu: List[float]
    sig: List[float]

    def transform(self, x: List[float]) -> List[float]:
        out = []
        for v, m, s in zip(x, self.mu, self.sig):
            if s <= 0:
                out.append(0.0)
            else:
                out.append((v - m) / s)
        return out


def fit_scaler(X: List[List[float]]) -> Scaler:
    if not X:
        return Scaler([], [])
    d = len(X[0])
    mu = [0.0] * d
    sig = [0.0] * d
    for j in range(d):
        col = [row[j] for row in X]
        mu[j] = sum(col) / len(col)
        # std
        if len(col) > 1:
            v = sum((c - mu[j]) ** 2 for c in col) / (len(col) - 1)
            sig[j] = math.sqrt(v) if v > 0 else 0.0
        else:
            sig[j] = 0.0
    return Scaler(mu=mu, sig=sig)


@dataclass
class LinearSGD:
    w: List[float]
    b: float = 0.0

    def predict_one(self, x: List[float]) -> float:
        return sum(wi * xi for wi, xi in zip(self.w, x)) + self.b


def fit_linear_sgd(
    X: List[List[float]],
    y: List[float],
    *,
    lr: float = 0.03,
    epochs: int = 800,
    l2: float = 1e-3,
) -> LinearSGD:
    if not X:
        return LinearSGD(w=[], b=0.0)
    d = len(X[0])
    w = [0.0] * d
    b = 0.0
    n = float(len(X))

    for _ in range(epochs):
        # full-batch gradients (stable for small datasets)
        gw = [0.0] * d
        gb = 0.0
        for xi, yi in zip(X, y):
            pred = sum(wj * xj for wj, xj in zip(w, xi)) + b
            err = pred - yi
            for j in range(d):
                gw[j] += (2.0 / n) * err * xi[j]
            gb += (2.0 / n) * err

        # L2
        for j in range(d):
            gw[j] += 2.0 * l2 * w[j]

        for j in range(d):
            w[j] -= lr * gw[j]
        b -= lr * gb

    return LinearSGD(w=w, b=b)


def sigmoid(z: float) -> float:
    z = max(-30.0, min(30.0, z))
    return 1.0 / (1.0 + math.exp(-z))


@dataclass
class LogisticSGD:
    w: List[float]
    b: float = 0.0

    def predict_proba_one(self, x: List[float]) -> float:
        return sigmoid(sum(wi * xi for wi, xi in zip(self.w, x)) + self.b)


def fit_logistic_sgd(
    X: List[List[float]],
    y: List[int],
    *,
    lr: float = 0.05,
    epochs: int = 1000,
    l2: float = 1e-3,
) -> LogisticSGD:
    if not X:
        return LogisticSGD(w=[], b=0.0)
    d = len(X[0])
    w = [0.0] * d
    b = 0.0
    n = float(len(X))

    for _ in range(epochs):
        gw = [0.0] * d
        gb = 0.0
        for xi, yi in zip(X, y):
            p = sigmoid(sum(wj * xj for wj, xj in zip(w, xi)) + b)
            err = p - float(yi)
            for j in range(d):
                gw[j] += (1.0 / n) * err * xi[j]
            gb += (1.0 / n) * err

        # L2
        for j in range(d):
            gw[j] += l2 * w[j]

        for j in range(d):
            w[j] -= lr * gw[j]
        b -= lr * gb

    return LogisticSGD(w=w, b=b)


# ----------------------------
# Public entrypoint
# ----------------------------
FEATURE_KEYS = [
    "moving_time_h",    # today
    "distance_km",
    "elevation_m",
    "sleep_h",
    "hrv",
    "rhr",
]


def _features_for_day(rows: List[Dict[str, Any]], i: int, risk_scores: List[float]) -> List[float]:
    r = rows[i]
    feats = []
    for k in FEATURE_KEYS:
        v = r.get(k)
        feats.append(float(v) if isinstance(v, (int, float)) else 0.0)

    # Add rolling features + risk proxy inputs
    w7 = _roll(rows, i, 7)
    w28 = _roll(rows, i, 28)

    feats.append(_sum_field(w7, "moving_time_h"))                 # load_7d_hours
    feats.append(_sum_field(_roll(rows, i, 3), "moving_time_h"))  # load_3d_hours

    s7 = _mean_field(w7, "sleep_h")
    s28 = _mean_field(w28, "sleep_h")
    feats.append(float((s7 - s28) if (s7 is not None and s28 is not None) else 0.0))  # sleep_delta7_28

    h7 = _mean_field(w7, "hrv")
    h28 = _mean_field(w28, "hrv")
    feats.append(float((h7 - h28) if (h7 is not None and h28 is not None) else 0.0))  # hrv_delta7_28

    feats.append(float(risk_scores[i]))  # current proxy risk score

    return feats


def run_forecasts(
    *,
    input_dir: Optional[str] = None,
    output_path: Optional[str] = None,
) -> Dict[str, Any]:
    base = input_dir or config.PROMPTING_DIRECTORY
    summary_p = os.path.join(base, "combined_summary.json")
    combined = load_json(summary_p, default=[])
    if not isinstance(combined, list):
        raise RuntimeError("combined_summary.json must be a list of day objects")

    rows = build_daily_rows(combined)
    if len(rows) < 35:
        raise RuntimeError(f"Need at least ~35 days of data for 7/28d windows. Got {len(rows)} days.")

    readiness = compute_proxy_readiness(rows)
    risk_scores = compute_proxy_risk_score(rows)

    # Threshold risk via quantile of your own history (no fixed number)
    thr = _quantile(risk_scores[:-1], 0.80) or 0.0

    # --- Build supervised datasets ---
    # Next-day readiness target: readiness[i+1]
    Xr: List[List[float]] = []
    yr1: List[float] = []
    yr7: List[float] = []

    # Overreach label: "high risk next 7 days" from proxy scores in the FUTURE window
    Xc: List[List[float]] = []
    yc: List[int] = []

    for i in range(0, len(rows) - 8):
        if readiness[i + 1] is None:
            continue
        # features at day i
        feats = _features_for_day(rows, i, risk_scores)

        # targets
        y1 = float(readiness[i + 1])
        y7_vals = [readiness[j] for j in range(i + 1, i + 8) if readiness[j] is not None]
        if not y7_vals:
            continue
        y7 = float(sum(y7_vals) / len(y7_vals))

        # classification label: any future day in next 7 exceeds risk threshold
        future_hi = any(risk_scores[j] >= thr for j in range(i + 1, i + 8))
        ycls = 1 if future_hi else 0

        Xr.append(feats)
        yr1.append(y1)
        yr7.append(y7)

        Xc.append(feats)
        yc.append(ycls)

    # Scale features + fit models (simple SGD)
    scaler = fit_scaler(Xr)
    Xr_s = [scaler.transform(x) for x in Xr]
    Xc_s = [scaler.transform(x) for x in Xc]

    reg1 = fit_linear_sgd(Xr_s, yr1)
    reg7 = fit_linear_sgd(Xr_s, yr7)
    clf = fit_logistic_sgd(Xc_s, yc)

    # --- Predict from latest day ---
    i_last = len(rows) - 1
    x_last = scaler.transform(_features_for_day(rows, i_last, risk_scores))
    pred_next_day = reg1.predict_one(x_last)
    pred_next_week = reg7.predict_one(x_last)
    risk_prob = clf.predict_proba_one(x_last)

    out = {
        "meta": {
            "today": rows[i_last]["date"],
            "input_dir": base,
            "proxy_risk_threshold_q80": thr,
        },
        "latest_observed": {
            "proxy_readiness_today": readiness[i_last],
            "proxy_risk_score_today": risk_scores[i_last],
            "proxy_high_risk_today": bool(risk_scores[i_last] >= thr),
        },
        "forecast": {
            "readiness_next_day": max(0.0, min(100.0, float(pred_next_day))),
            "readiness_next_week_mean": max(0.0, min(100.0, float(pred_next_week))),
            "overreach_risk_prob_next_7d": float(risk_prob),
            "overreach_risk_high_next_7d": bool(risk_prob >= 0.5),
        },
        "notes": [
            "Readiness is a proxy score derived from sleep/HRV/RHR and recent load windows (7d vs 28d).",
            "Overreach risk is trained on proxy 'risk score' events (high load + sleep drop + HRV drop), then converted to a probability.",
            "This is not medical advice; it is a training/fatigue risk heuristic based on available data.",
        ],
    }

    outp = output_path or os.path.join(base, "readiness_and_risk_forecast.json")
    save_json(outp, out, compact=False)
    return {"saved": outp, "result": out}


def main() -> None:
    # Convenience if you want to call as a script during dev
    r = run_forecasts()
    print(f"[Saved] {r['saved']}")