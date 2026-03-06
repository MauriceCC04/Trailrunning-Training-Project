# Trailrunning Training Project — User Guide

This project pulls your training + wellness data (Garmin or Intervals.icu + Strava), combines it into a clean dataset, and optionally runs an LLM “coach” to generate training plans, recovery status, and meal plans.

It supports **multi-user profiles** (separate tokens, data folders, and GarminDb configs per user) via `--profile`.

---

## Prerequisites

- **Python 3.9+**
- A **Strava API application** (Client ID + Client Secret)
- One of:
  - **GarminDb** installed and its CLI available (`garmindb_cli` or `garmindb_cli.py`)
  - **Intervals.icu** API access (API key + athlete ID) as an alternative

Optional:
- **OpenAI API key** for the LLM coach feature

---

## Installation (macOS / Linux)

Clone the repo and create a virtual environment:

```bash
cd /.../Trailrunning-Training-Project

python3 -m venv .venv
source .venv/bin/activate

python -m pip install --upgrade pip
pip install -r requirements.txt
pip install -e .
````

Verify the CLI:

```bash
trailtraining -h
```

---

## Profiles (multi-user support)

Profiles make it easy to run the tool for multiple people on the same machine.

### How profiles work

When you run:

```bash
trailtraining --profile alice run-all
```

the CLI will:

1. Load environment variables from:

   * `~/.trailtraining/profiles/alice.env` (if it exists)
2. Use an isolated default data directory (unless you override it):

   * `~/trailtraining-data/alice/`
3. Keep Strava tokens per profile:

   * `~/trailtraining-data/alice/tokens/strava_token.json`
4. Store a per-profile GarminDb config at:

   * `~/.trailtraining/garmin/alice/GarminConnectConfig.json`
     and activate it for GarminDb automatically.

### Create profile files

Create the profile folder:

```bash
mkdir -p ~/.trailtraining/profiles
```

Create one env file per user, e.g. `~/.trailtraining/profiles/alice.env`:

```bash
# --- Required for Strava ---
STRAVA_CLIENT_ID="..."
STRAVA_CLIENT_SECRET="..."
STRAVA_REDIRECT_URI="http://127.0.0.1:5000/authorization"

# --- Choose ONE wellness provider ---
# Option A: Garmin
GARMIN_EMAIL="alice@example.com"
GARMIN_PASSWORD="..."

# Option B: Intervals.icu (instead of Garmin)
# INTERVALS_API_KEY="..."
# INTERVALS_ATHLETE_ID="..."

# --- Optional LLM coach ---
OPENAI_API_KEY="..."
TRAILTRAINING_LLM_MODEL="gpt-5.2"
TRAILTRAINING_REASONING_EFFORT="medium"   # none|low|medium|high|xhigh
TRAILTRAINING_VERBOSITY="medium"          # low|medium|high

# Optional override: where this profile stores all data
# TRAILTRAINING_BASE_DIR="$HOME/trailtraining-data/alice"
```

Repeat for `bob.env`, etc.

> **Note (Garmin concurrency):** GarminDb reads a single “active” config at `~/.GarminDb/GarminConnectConfig.json`. The pipeline switches this for you per profile, so **don’t run two Garmin profile downloads at the same time** on the same machine unless you isolate HOME (container / separate OS user).

---

## Strava setup (required)

1. Create a Strava API application and copy:

   * `STRAVA_CLIENT_ID`
   * `STRAVA_CLIENT_SECRET`
2. Use redirect URI:

   * `http://127.0.0.1:5000/authorization`

For each profile, run the auth flow once:

```bash
trailtraining --profile alice auth-strava
trailtraining --profile bob auth-strava
```

This writes a token file inside that profile’s data directory.

---

## GarminDb setup (if using Garmin)

Install GarminDb according to its docs, and make sure the CLI is on your PATH:

* `garmindb_cli` or `garmindb_cli.py`

If it isn’t on your PATH, set:

```bash
export GARMINGDB_CLI="/full/path/to/garmindb_cli"
```

You do **NOT** need to manually create `~/.GarminDb/GarminConnectConfig.json` anymore.
The pipeline writes a per-profile config and activates it automatically.

---

## Running the full pipeline (Garmin → Strava → Combine)

```bash
trailtraining --profile alice run-all
```

First run may take a while (Garmin download/import). Subsequent runs are incremental.

Cleaning options:

```bash
trailtraining --profile alice run-all --clean
trailtraining --profile alice run-all --clean-processing
trailtraining --profile alice run-all --clean-prompting
```

---

## Intervals.icu alternative (faster wellness fetch)

If you use Intervals.icu, set these in your profile env instead of Garmin credentials:

```bash
INTERVALS_API_KEY="..."
INTERVALS_ATHLETE_ID="..."
```

(Optional) date range:

```bash
TRAILTRAINING_WELLNESS_OLDEST="2023-01-01"
TRAILTRAINING_WELLNESS_NEWEST="2026-02-27"
```

Fetch wellness only:

```bash
trailtraining --profile alice fetch-intervals --oldest "2023-01-01" --newest "2026-02-27"
```

Or run the full Intervals pipeline (Intervals → Strava → Combine):

```bash
trailtraining --profile alice run-all-intervals
```

This is typically much faster than GarminDb, but may include less wellness detail depending on your Intervals data.

---

## LLM coach (optional)

Set in your profile env:

```bash
OPENAI_API_KEY="..."
TRAILTRAINING_LLM_MODEL="gpt-5.2"
TRAILTRAINING_REASONING_EFFORT="medium"   # none|low|medium|high|xhigh
TRAILTRAINING_VERBOSITY="medium"          # low|medium|high
```

Run prompts:

```bash
trailtraining --profile alice coach --prompt training-plan
trailtraining --profile alice coach --prompt recovery-status
trailtraining --profile alice coach --prompt meal-plan
```

What they do:

* `training-plan` → generates a training plan
* `recovery-status` → analyzes fatigue and recovery
* `meal-plan` → suggests meals based on training + recovery data

If you want to change bewteen triathlon or trailrunning prompting styles, you can set:

```bash
TRAILTRAINING_PROMPTING_STYLE="triathlon"
export TRAILTRAINING_COACH_STYLE="trailrunning"
```
or use it via the cli:
```bash
trailtraining --profile alice coach --prompt training-plan   # triathlon
trailtraining --profile bob   coach --prompt training-plan   # trailrunning
```

If you need to point at a specific prompting directory/zip:

```bash
trailtraining --profile alice coach --prompt recovery-status --input /path/to/prompting/
```

---

## Helpful commands

```bash
trailtraining -h
trailtraining run-all -h
trailtraining fetch-intervals -h
trailtraining run-all-intervals -h
trailtraining coach -h
```

---

## Notes

* The project is commonly configured to only download data starting around **Dec 2023** to limit volume and keep LLM prompts focused. You can adjust date ranges if desired.
* Prompting can be customized for different sports or preferences by editing the prompting templates/inputs in the project’s prompting outputs.

---

