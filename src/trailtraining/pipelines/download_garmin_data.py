"""
Configuration script for GarminDb. Writes config to ~/.GarminDb/GarminConnectConfig.json.
Avoids hardcoding sensitive information.
"""

import os
import json
from trailtraining import config


def write_config():
    CONFIG_DIR = os.path.expanduser("~/.GarminDb")
    os.makedirs(CONFIG_DIR, exist_ok=True)

    configuration = {
        "db": {"type": "sqlite"},
        "garmin": {"domain": "garmin.com"},
        "credentials": {
            "user": config.GARMIN_EMAIL,
            "secure_password": False,
            "password": config.GARMIN_PASSWORD,  # Do not hardcode passwords
            "password_file": None
        },
        "data": {
            "weight_start_date": "07/08/2025",
            "sleep_start_date": "12/25/2023",
            "rhr_start_date": "12/25/2023",
            "monitoring_start_date": "12/25/2023",
            "download_latest_activities": 25,
            "download_all_activities": 1000
        },
        "directories": {
            "relative_to_home": False,
            "base_dir": config.BASE_DIR,
            "mount_dir": "/Volumes/GARMIN"
        },
        "enabled_stats": {
            "monitoring": False,
            "steps": False,
            "itime": False,
            "sleep": True,
            "rhr": True,
            "weight": False,
            "activities": False
        },
        "course_views": {"steps": []},
        "modes": {},
        "activities": {"display": []},
        "settings": {
            "metric": False,
            "default_display_activities": ["walking", "running", "cycling"]
        },
        "checkup": {"look_back_days": 90}
    }

    with open(os.path.join(CONFIG_DIR, "GarminConnectConfig.json"), "w", encoding="utf-8") as file:
        json.dump(configuration, file, indent=4)

# To download and import all data from Garmin Connect, run:
#   garmindb_cli.py --all --download --import --analyze
# To incrementally update your db:
#   garmindb_cli.py --all --download --import --analyze --latest
# To backup your DB files:
#   garmindb_cli.py --backup