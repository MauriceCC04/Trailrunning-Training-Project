# src/trailtraining/config.py
# Centralized configuration for directory paths and credentials

from __future__ import annotations

import os
from pathlib import Path


def _env(name: str, default: str = "") -> str:
    return (os.getenv(name, default) or "").strip()


# Prefer TRAILTRAINING_BASE_DIR (documented in README), but keep compatibility with TRAILTRAINING_DATA_DIR.
_base = _env("TRAILTRAINING_BASE_DIR") or _env("TRAILTRAINING_DATA_DIR", "~/trailtraining-data")
BASE_DIR_PATH = Path(_base).expanduser().resolve()

# Legacy string variables used across the repo
BASE_DIR = str(BASE_DIR_PATH)

RHR_DIRECTORY = os.path.join(BASE_DIR, "RHR")
SLEEP_DIRECTORY = os.path.join(BASE_DIR, "Sleep")
FIT_DIRECTORY = os.path.join(BASE_DIR, "FitFiles")

PROCESSING_DIRECTORY = os.path.join(BASE_DIR, "processing")
PROMPTING_DIRECTORY = os.path.join(BASE_DIR, "prompting")

# Credentials (read from environment)
STRAVA_ID = int(_env("STRAVA_CLIENT_ID", "0") or "0")
STRAVA_SECRET = _env("STRAVA_CLIENT_SECRET", "")
STRAVA_REDIRECT_URI = _env("STRAVA_REDIRECT_URI", "http://localhost:8000/callback")

GARMIN_EMAIL = _env("GARMIN_EMAIL", "")
GARMIN_PASSWORD = _env("GARMIN_PASSWORD", "")


def ensure_directories() -> None:
    """Create all expected directories."""
    for d in [
        BASE_DIR,
        RHR_DIRECTORY,
        SLEEP_DIRECTORY,
        FIT_DIRECTORY,
        PROCESSING_DIRECTORY,
        PROMPTING_DIRECTORY,
    ]:
        os.makedirs(d, exist_ok=True)
