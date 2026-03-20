from __future__ import annotations

from trailtraining.llm.soft_eval import _build_batch_prompt


def _minimal_plan() -> dict:
    return {
        "meta": {
            "today": "2026-03-13",
            "plan_start": "2026-03-14",
            "plan_days": 7,
            "style": "trailrunning",
            "primary_goal": "to become a faster trail runner",
        },
        "snapshot": {
            "last7": {
                "distance_km": "22",
                "moving_time_hours": "2.2",
                "elevation_m": "300",
                "activity_count": "2",
                "sleep_hours_mean": "",
                "hrv_mean": "",
                "rhr_mean": "46",
            },
            "baseline28": {
                "distance_km": "18",
                "moving_time_hours": "1.9",
                "elevation_m": "220",
                "activity_count": "2",
                "sleep_hours_mean": "",
                "hrv_mean": "",
                "rhr_mean": "45",
            },
            "notes": "",
        },
        "readiness": {"status": "steady", "rationale": "Test.", "signal_ids": []},
        "plan": {
            "weekly_totals": {
                "planned_distance_km": 30.0,
                "planned_moving_time_hours": 4.5,
                "planned_elevation_m": 600.0,
            },
            "days": [
                {
                    "date": "2026-03-14",
                    "title": "Easy run",
                    "session_type": "easy",
                    "is_rest_day": False,
                    "is_hard_day": False,
                    "duration_minutes": 45,
                    "target_intensity": "easy",
                    "terrain": "road",
                    "workout": "45 min easy",
                    "purpose": "aerobic maintenance",
                    "signal_ids": [],
                }
            ],
        },
        "recovery": {"actions": [], "signal_ids": []},
        "risks": [],
        "data_notes": [],
        "citations": [],
    }


def test_build_batch_prompt_includes_few_shot_examples() -> None:
    prompt = _build_batch_prompt(
        ["goal_alignment", "plan_coherence"],
        _minimal_plan(),
        {"score": 100, "grade": "A", "subscores": {}, "violations": []},
        rollups=None,
        style="trailrunning",
        primary_goal="to become a faster trail runner",
        lifestyle_notes="",
    )

    assert "## Few-shot examples (illustrative mini-cases)" in prompt
    assert "Example A - stronger goal/coherence case" in prompt
    assert "Example B - weaker goal/coherence case" in prompt
    assert '"marker_results"' in prompt
