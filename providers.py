from __future__ import annotations

import os
from typing import Optional

from trailtraining import config


def detect_wellness_provider(explicit: Optional[str] = None) -> str:
    v = (
        (
            explicit
            or os.getenv("TRAILTRAINING_WELLNESS_PROVIDER")
            or os.getenv("WELLNESS_PROVIDER")
            or "auto"
        )
        .strip()
        .lower()
    )
    if v in {"garmin", "intervals"}:
        return v
    if (config.INTERVALS_API_KEY or "").strip():
        return "intervals"
    if (config.GARMIN_EMAIL or "").strip() and (config.GARMIN_PASSWORD or "").strip():
        return "garmin"
    return "intervals"
