# config.py
# Centralized configuration for directory paths and other settings

import os

# src/trailtraining/config.py
import os

BASE_DIR = os.path.abspath(os.path.expanduser(
    os.environ.get("TRAILTRAINING_DATA_DIR", "~/trailtraining-data")
))

RHR_DIRECTORY = os.path.join(BASE_DIR, "RHR")
SLEEP_DIRECTORY = os.path.join(BASE_DIR, "Sleep")
FIT_DIRECTORY = os.path.join(BASE_DIR, "FitFiles")
PROCESSING_DIRECTORY = os.path.join(BASE_DIR, "processing")
PROMPTING_DIRECTORY = os.path.join(BASE_DIR, "prompting")

STRAVA_ID = int(os.environ.get("STRAVA_CLIENT_ID", "0"))
STRAVA_SECRET = os.environ.get("STRAVA_CLIENT_SECRET", "")
GARMIN_EMAIL = os.environ.get("GARMIN_EMAIL", "")
GARMIN_PASSWORD = os.environ.get("GARMIN_PASSWORD", "")

