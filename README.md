# trailtraining

[![CI](../../actions/workflows/ci.yml/badge.svg)](../../actions/workflows/ci.yml)

`trailtraining` is a Python CLI for building local training datasets from Strava plus either GarminDB or Intervals.icu. It can also generate readiness forecasts, structured coaching outputs, and rule-based evaluations of generated plans.

## Features

- Pulls activities from Strava
- Pulls wellness data from GarminDB or Intervals.icu
- Merges data into local JSON artifacts
- Computes readiness and overreach-risk forecasts
- Generates structured coaching outputs
- Evaluates training plans against simple safety rules
- Supports isolated multi-profile setups with `--profile`

## Repo layout

```text
.
├── .github/workflows/
├── demo/
├── src/trailtraining/
├── tests/
├── README.md
└── pyproject.toml
````

## Requirements

* Python 3.9+
* A Strava API application
* One wellness source:

  * GarminDB, or
  * Intervals.icu API access
* An OpenAI API key for `coach`

## Installation

```bash
git clone https://github.com/MauriceCC04/trailtraining.git
cd trailtraining

python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
pip install -e .
```

Optional extras:

```bash
pip install -e ".[dev]"
pip install -e ".[analysis]"
```

Verify installation:

```bash
trailtraining -h
```

## Configuration

Profiles load environment variables from:

```text
~/.trailtraining/profiles/<profile>.env
```

Example:

```bash
mkdir -p ~/.trailtraining/profiles
nano ~/.trailtraining/profiles/alice.env
```

Minimal example:

```bash
STRAVA_CLIENT_ID="..."
STRAVA_CLIENT_SECRET="..."
STRAVA_REDIRECT_URI="http://127.0.0.1:5000/authorization"

# Choose one wellness source

# Garmin
GARMIN_EMAIL="alice@example.com"
GARMIN_PASSWORD="..."

# or Intervals.icu
# INTERVALS_API_KEY="..."
# INTERVALS_ATHLETE_ID="0"

OPENAI_API_KEY="..."
```

By default, per-profile data is stored under:

```text
~/trailtraining-data/<profile>
```

## Quickstart

Check setup:

```bash
trailtraining --profile alice doctor
```

Authorize Strava once:

```bash
trailtraining --profile alice auth-strava
```

Run the full pipeline:

```bash
trailtraining --profile alice run-all
```

Force a wellness provider if needed:

```bash
trailtraining --profile alice run-all --wellness-provider intervals
trailtraining --profile alice run-all --wellness-provider garmin
```

Generate a forecast:

```bash
trailtraining --profile alice forecast
```

Generate a training plan:

```bash
trailtraining --profile alice coach --prompt training-plan
```

Evaluate a generated plan:

```bash
trailtraining --profile alice eval-coach \
  --input ~/trailtraining-data/alice/prompting/coach_brief_training-plan.json
```

## What it produces

Typical outputs live under:

```text
~/trailtraining-data/<profile>/
├── processing/
└── prompting/
```

The `demo/` directory contains representative artifacts you can inspect without credentials.

## Command reference

Core commands:

```bash
trailtraining --profile alice doctor
trailtraining --profile alice auth-strava
trailtraining --profile alice fetch-strava
trailtraining --profile alice fetch-garmin
trailtraining --profile alice fetch-intervals
trailtraining --profile alice combine
trailtraining --profile alice run-all
trailtraining --profile alice run-all-intervals
trailtraining --profile alice forecast
trailtraining --profile alice coach --prompt training-plan
trailtraining --profile alice eval-coach --input <path>
```

Useful options:

```bash
trailtraining --profile alice run-all --clean
trailtraining --profile alice run-all --clean-processing
trailtraining --profile alice run-all --clean-prompting
trailtraining --profile alice fetch-intervals --oldest 2025-01-01 --newest 2025-03-01
trailtraining --profile alice coach --prompt training-plan --style trailrunning
trailtraining --profile alice coach --prompt training-plan --style triathlon
```

## Development

Install dev dependencies:

```bash
pip install -e ".[dev]"
pre-commit install
```

Run checks:

```bash
pytest
ruff check .
mypy src
```

## Limitations

* Requires user-managed API credentials and local setup
* Data quality depends on upstream providers
* Coaching outputs are experimental
* Garmin workflows depend on GarminDB

## Safety

This project is a personal training-data and planning tool. It is not medical software, and generated outputs should not be treated as medical advice.

## License

MIT
