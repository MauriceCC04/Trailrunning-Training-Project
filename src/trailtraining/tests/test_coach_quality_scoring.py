from trailtraining.llm.constraints import ConstraintConfig, evaluate_training_plan_quality


def test_quality_scoring_report_shape_and_score():
    rollups = {"windows": {"7": {"activities": {"total_moving_time_hours": 10.0}}}}

    plan_obj = {
        "plan": {
            "weekly_totals": {"planned_moving_time_hours": 12.0},
            "days": [
                # 7 days, 0 rest days, 4 hard days, missing signal_ids -> should score < 100
                {
                    "date": "2026-03-01",
                    "is_hard_day": True,
                    "is_rest_day": False,
                    "duration_minutes": 60,
                    "session_type": "tempo",
                    "signal_ids": [],
                },
                {
                    "date": "2026-03-02",
                    "is_hard_day": True,
                    "is_rest_day": False,
                    "duration_minutes": 60,
                    "session_type": "intervals",
                    "signal_ids": [],
                },
                {
                    "date": "2026-03-03",
                    "is_hard_day": True,
                    "is_rest_day": False,
                    "duration_minutes": 60,
                    "session_type": "hills",
                    "signal_ids": [],
                },
                {
                    "date": "2026-03-04",
                    "is_hard_day": True,
                    "is_rest_day": False,
                    "duration_minutes": 60,
                    "session_type": "tempo",
                    "signal_ids": [],
                },
                {
                    "date": "2026-03-05",
                    "is_hard_day": False,
                    "is_rest_day": False,
                    "duration_minutes": 45,
                    "session_type": "easy",
                    "signal_ids": [],
                },
                {
                    "date": "2026-03-06",
                    "is_hard_day": False,
                    "is_rest_day": False,
                    "duration_minutes": 45,
                    "session_type": "easy",
                    "signal_ids": [],
                },
                {
                    "date": "2026-03-07",
                    "is_hard_day": False,
                    "is_rest_day": False,
                    "duration_minutes": 45,
                    "session_type": "easy",
                    "signal_ids": [],
                },
            ],
        },
        "citations": [],
    }

    cfg = ConstraintConfig(max_ramp_pct=10.0, max_consecutive_hard=2)
    report = evaluate_training_plan_quality(plan_obj, rollups, cfg)

    assert "score" in report and "violations" in report
    assert isinstance(report["violations"], list)
    assert report["score"] < 100
