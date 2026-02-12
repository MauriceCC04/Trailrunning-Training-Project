# src/trailtraining/cli.py
import argparse
import importlib
import sys
import os

def _run(func):
    try:
        func()
    except SystemExit as e:
        raise
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)

def cmd_auth_strava(_args):
    # Your strava pipeline handles auth flow already
    from trailtraining.pipelines import strava
    _run(strava.main)

def cmd_fetch_strava(_args):
    from trailtraining.pipelines import strava
    _run(strava.main)

def cmd_fetch_garmin(_args):
    from trailtraining.pipelines import garmin
    _run(garmin.main)

def cmd_combine(_args):
    from trailtraining.data import combine
    _run(combine.main)

def cmd_run_all(_args):
    from trailtraining.pipelines import run_all
    _run(run_all.main)


def cmd_coach(args):
    from trailtraining.llm.coach import CoachConfig, run_coach_brief

    cfg = CoachConfig(
        model=args.model,
        reasoning_effort=args.reasoning_effort,
        verbosity=args.verbosity,
        days=args.days,
        max_chars=args.max_chars,
        temperature=args.temperature,
    )
    text, out_path = run_coach_brief(
        prompt=args.prompt,
        cfg=cfg,
        input_path=args.input,
        personal_path=args.personal,
        summary_path=args.summary,
        output_path=args.output,
    )
    print(text)
    if out_path:
        print(f"\n[Saved] {out_path}")



def main(argv=None):
    parser = argparse.ArgumentParser(prog="trailtraining", description="TrailTraining CLI")
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("auth-strava", help="Run Strava auth flow (opens local server)").set_defaults(func=cmd_auth_strava)
    sub.add_parser("fetch-strava", help="Fetch activities from Strava").set_defaults(func=cmd_fetch_strava)
    sub.add_parser("fetch-garmin", help="Fetch/process data from Garmin").set_defaults(func=cmd_fetch_garmin)
    sub.add_parser("combine", help="Combine Garmin + Strava JSONs").set_defaults(func=cmd_combine)
    sub.add_parser("run-all", help="Run full pipeline (Garmin → Strava → Combine)").set_defaults(func=cmd_run_all)
    #sub.add_parser("train-fatigue", help="Run fatigue model script").set_defaults(func=cmd_train_fatigue)
    coach_p = sub.add_parser("coach", help="LLM coach analysis on combined_summary.json + formatted_personal_data.json")
    coach_p.add_argument("--prompt", default="training-plan",
                         choices=["training-plan", "recovery-status", "meal-plan"])
    coach_p.add_argument("--model", default=os.getenv("TRAILTRAINING_LLM_MODEL", "gpt-5.2"))
    coach_p.add_argument("--reasoning-effort", default=os.getenv("TRAILTRAINING_REASONING_EFFORT", "medium"),
                         choices=["none", "low", "medium", "high", "xhigh"])
    coach_p.add_argument("--verbosity", default=os.getenv("TRAILTRAINING_VERBOSITY", "medium"),
                         choices=["low", "medium", "high"])
    coach_p.add_argument("--temperature", type=float, default=None,
                         help="Only used if --reasoning-effort none (API restriction).")
    coach_p.add_argument("--days", type=int, default=int(os.getenv("TRAILTRAINING_COACH_DAYS", "60")))
    coach_p.add_argument("--max-chars", type=int, default=int(os.getenv("TRAILTRAINING_COACH_MAX_CHARS", "200000")))
    coach_p.add_argument("--output", default=None,
                         help="Output markdown file. Default: <prompting_dir>/coach_brief_<prompt>.md")
    coach_p.add_argument("--input", default=None,
                         help="Directory OR .zip containing the two JSON files. Default: prompting directory")
    coach_p.add_argument("--personal", default=None,
                         help="Explicit path to formatted_personal_data.json (overrides --input)")
    coach_p.add_argument("--summary", default=None,
                         help="Explicit path to combined_summary.json (overrides --input)")
    coach_p.set_defaults(func=cmd_coach)

    args = parser.parse_args(argv)
    args.func(args)

if __name__ == "__main__":
    main()
