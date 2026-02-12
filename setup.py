# setup.py
from setuptools import setup, find_packages

setup(
    name="trailtraining",
    version="0.1.0",
    description="Pipelines for Garmin/Strava + fatigue modeling",
    packages=find_packages(where="src"),
    package_dir={"": "src"},
    entry_points={
        "console_scripts": [
            "trailtraining=trailtraining.cli:main",
        ],
    },
)
