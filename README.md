# trailtraining

![CI](https://github.com/MauriceCC04/trailtraining/actions/workflows/ci.yml/badge.svg)

A local-first Python CLI that turns Strava/Garmin training data into auditable coaching artifacts — structured plans, deterministic evaluation, and iterative revision.

Most AI coaching features are generic and unverifiable. This project is an attempt to build something better: every output is grounded in local data, checked against explicit constraints, and revisable from its own evaluation report.

→ **No API keys needed to see what it produces.** Check out [`demo/`](demo) and [`docs/engineering.md`](docs/engineering.md).

---

## How it works

```
Strava / Garmin / Intervals.icu
        │
        ▼
   local ingestion
        │
        ▼
  combine → combined_rollups.json + formatted_personal_data.json
        │
        ▼
  deterministic forecast (readiness + overreach risk)
        │
        ▼
  coach --prompt training-plan
        │
        ├──► coach_brief_training-plan.json / .txt
        │
        ▼
  eval-coach [--soft-eval]
        │
        ├──► eval_report.json
        │
        ▼
  revise-plan
        │
        └──► revised-plan.json / .txt
```

The pipeline runs in one direction: ingest → forecast → generate → evaluate → revise. Generated plans are treated as first drafts, not final answers.

---

## Engineering decisions worth noting

**Deterministic constraints before generation.** Ramp rate, hard-day spacing, and rest structure are enforced mathematically on the output — not left to the model's judgment. The model sees the constraints in its context; if it still violates them, guardrails correct in-place.

**Two-stage evaluation.** `eval-coach` runs deterministic checks (ramp %, consecutive hard days, citation coverage). With `--soft-eval`, a second model acts as an independent judge using a rubric-driven schema — strengths, concerns, marker-level evidence. The soft evaluator can be a different model family than the generator.

**Revision is part of the pipeline.** `revise-plan` takes the original plan and its eval report and produces a revised artifact. Generate → critique → revise → re-check is the intended loop, not a nice-to-have.

**Structured contracts throughout.** Artifacts are validated with strict Pydantic models. The LLM is prompted with a JSON schema and the output is validated on the way out — malformed responses trigger a repair pass before anything is saved.

**Graceful degradation.** The pipeline runs on activity-only data and improves when sleep, HRV, or resting HR are available. Missing recovery telemetry is surfaced explicitly in the output rather than silently omitted.

---

## Setup

**Requirements:** Python 3.9+, a Strava API application, one wellness source (GarminDB or Intervals.icu), an OpenRouter API key.

```bash
git clone https://github.com/MauriceCC04/trailtraining.git
cd trailtraining
python3 -m venv .venv && source .venv/bin/activate
pip install -e .
```

Profiles load from `~/.trailtraining/profiles/<profile>.env`:

```bash
STRAVA_CLIENT_ID="..."
STRAVA_CLIENT_SECRET="..."
STRAVA_REDIRECT_URI="http://127.0.0.1:5000/authorization"

# Intervals.icu (or use Garmin equivalents)
INTERVALS_API_KEY="..."
INTERVALS_ATHLETE_ID="0"

OPENROUTER_API_KEY="sk-or-v1-..."
TRAILTRAINING_LLM_MODEL="openai/gpt-4o"
TRAILTRAINING_SOFT_EVAL_MODEL="anthropic/claude-sonnet-4-6"
```

---

## Typical workflow

```bash
trailtraining --profile alice doctor          # check setup
trailtraining --profile alice auth-strava     # OAuth flow
trailtraining --profile alice run-all         # ingest + combine
trailtraining --profile alice forecast        # readiness + overreach risk
trailtraining --profile alice coach --prompt training-plan
trailtraining --profile alice eval-coach --soft-eval
trailtraining --profile alice revise-plan
trailtraining --profile alice eval-coach \
  --input ~/trailtraining-data/alice/prompting/revised-plan.json
```

Other prompts: `recovery-status`, `meal-plan`, `session-review`.

---

## Output layout

```
~/trailtraining-data/<profile>/prompting/
├── combined_rollups.json
├── formatted_personal_data.json
├── readiness_and_risk_forecast.json
├── coach_brief_training-plan.json / .txt
├── eval_report.json
├── revised-plan.json / .txt
└── coach_brief_<recovery-status|meal-plan|session-review>.md
```

---

## Stack

Python 3.9–3.12 · Pydantic v2 · OpenAI SDK (OpenRouter) · Flask (OAuth callback) · pytest · ruff · mypy

---

## Limitations

- Requires user-managed credentials and local setup to run
- Load modeling is intentionally simple (moving time × intensity proxy)
- Not medical software — outputs should be reviewed with common sense

## License

MIT
