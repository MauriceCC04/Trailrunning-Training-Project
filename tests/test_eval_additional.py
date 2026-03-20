from __future__ import annotations

import json
from pathlib import Path

import pytest
from trailtraining.llm.constraints import ConstraintConfig
from trailtraining.llm.eval import (
    SoftEvalConfig,
    _compute_marker_variance,
    _load_rollups_near,
    evaluate_training_plan_file,
    evaluate_training_plan_quality_file,
)

from tests._artifact_builders import make_training_plan_artifact


def test_load_rollups_near_prefers_explicit_path(tmp_path: Path) -> None:
    plan_path = tmp_path / "plan.json"
    plan_path.write_text("{}", encoding="utf-8")
    explicit = tmp_path / "rollups-explicit.json"
    explicit.write_text(json.dumps({"windows": {"7": {}}}), encoding="utf-8")

    loaded = _load_rollups_near(plan_path, str(explicit))

    assert loaded == {"windows": {"7": {}}}


def test_load_rollups_near_uses_sibling_combined_rollups(tmp_path: Path) -> None:
    plan_path = tmp_path / "plan.json"
    plan_path.write_text("{}", encoding="utf-8")
    sibling = tmp_path / "combined_rollups.json"
    sibling.write_text(json.dumps({"windows": {"28": {}}}), encoding="utf-8")

    loaded = _load_rollups_near(plan_path)

    assert loaded == {"windows": {"28": {}}}


def test_evaluate_training_plan_file_rejects_non_object(tmp_path: Path) -> None:
    input_path = tmp_path / "plan.json"
    input_path.write_text(json.dumps([]), encoding="utf-8")

    with pytest.raises(ValueError, match="Coach JSON must be an object"):
        evaluate_training_plan_file(str(input_path))


def test_compute_marker_variance_returns_per_marker_std() -> None:
    runs = [
        [{"marker_id": "m1", "score": 1}, {"marker_id": "m2", "score": 5}],
        [{"marker_id": "m1", "score": 3}, {"marker_id": "m2", "score": 5}],
        [{"marker_id": "m1", "score": 5}, {"marker_id": "m2", "score": 5}],
    ]

    variance = _compute_marker_variance(runs)

    assert variance["m1"] > 0.0
    assert variance["m2"] == 0.0


def test_evaluate_training_plan_quality_file_records_soft_eval_error(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import trailtraining.llm.eval as eval_mod

    plan = make_training_plan_artifact()
    plan_path = tmp_path / "plan.json"
    plan_path.write_text(json.dumps(plan), encoding="utf-8")

    def fake_soft_eval(*args, **kwargs):
        raise RuntimeError("boom")

    monkeypatch.setattr(eval_mod, "evaluate_training_plan_soft", fake_soft_eval)

    report, _ = evaluate_training_plan_quality_file(
        str(plan_path),
        cfg=ConstraintConfig(min_signal_ids_per_day=0),
        soft_eval_cfg=SoftEvalConfig(enabled=True),
    )

    assert report["stats"]["soft_eval_error"] == "boom"
    assert report.get("soft_assessment") is None


def test_evaluate_training_plan_quality_file_multi_run_builds_consensus(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import trailtraining.llm.eval as eval_mod

    plan = make_training_plan_artifact()
    plan_path = tmp_path / "plan.json"
    plan_path.write_text(json.dumps(plan), encoding="utf-8")

    assessments = [
        {
            "model": "fake-model",
            "style": "trailrunning",
            "primary_goal": "build trail endurance",
            "summary": "run 1 summary",
            "overall_score": 60,
            "grade": "D",
            "confidence": "low",
            "rubric_scores": {
                "goal_alignment": {"score": 40, "reasoning": "weak alignment"},
                "plan_coherence": {"score": 40, "reasoning": "weak coherence"},
                "explanation_quality": {"score": 40, "reasoning": "weak explanation"},
                "caution_proportionality": {"score": 40, "reasoning": "weak caution"},
                "actionability": {"score": 40, "reasoning": "weak actionability"},
            },
            "marker_results": [
                {
                    "rubric": "goal_alignment",
                    "marker_id": "goal_specificity",
                    "marker": "Goal specificity",
                    "verdict": "fail",
                    "score": 1,
                    "observation": "obs 1",
                    "evidence": "ev 1",
                    "improvement_hint": "hint 1",
                }
            ],
            "strengths": ["Clear structure"],
            "concerns": ["Too generic"],
            "suggested_improvements": ["Clarify purpose"],
            "repaired": False,
            "derived_fields": [],
        },
        {
            "model": "fake-model",
            "style": "trailrunning",
            "primary_goal": "build trail endurance",
            "summary": "run 2 summary",
            "overall_score": 80,
            "grade": "B",
            "confidence": "high",
            "rubric_scores": {
                "goal_alignment": {"score": 80, "reasoning": "ok"},
                "plan_coherence": {"score": 80, "reasoning": "ok"},
                "explanation_quality": {"score": 80, "reasoning": "ok"},
                "caution_proportionality": {"score": 80, "reasoning": "ok"},
                "actionability": {"score": 80, "reasoning": "ok"},
            },
            "marker_results": [
                {
                    "rubric": "goal_alignment",
                    "marker_id": "goal_specificity",
                    "marker": "Goal specificity",
                    "verdict": "partial",
                    "score": 3,
                    "observation": "obs 2",
                    "evidence": "ev 2",
                    "improvement_hint": "hint 2",
                }
            ],
            "strengths": ["Clear structure", "Goal-focused sessions"],
            "concerns": ["Some wording still generic"],
            "suggested_improvements": ["Clarify purpose", "Add one terrain cue"],
            "repaired": False,
            "derived_fields": [],
        },
        {
            "model": "fake-model",
            "style": "trailrunning",
            "primary_goal": "build trail endurance",
            "summary": "run 3 summary",
            "overall_score": 100,
            "grade": "A",
            "confidence": "high",
            "rubric_scores": {
                "goal_alignment": {"score": 100, "reasoning": "strong"},
                "plan_coherence": {"score": 100, "reasoning": "strong"},
                "explanation_quality": {"score": 100, "reasoning": "strong"},
                "caution_proportionality": {"score": 100, "reasoning": "strong"},
                "actionability": {"score": 100, "reasoning": "strong"},
            },
            "marker_results": [
                {
                    "rubric": "goal_alignment",
                    "marker_id": "goal_specificity",
                    "marker": "Goal specificity",
                    "verdict": "pass",
                    "score": 5,
                    "observation": "obs 3",
                    "evidence": "ev 3",
                    "improvement_hint": "hint 3",
                }
            ],
            "strengths": ["Goal-focused sessions"],
            "concerns": ["Minor wording issue"],
            "suggested_improvements": ["Add one terrain cue"],
            "repaired": False,
            "derived_fields": [],
        },
    ]
    call_count = {"n": 0}

    def fake_soft_eval(*args, **kwargs):
        idx = call_count["n"]
        call_count["n"] += 1
        return assessments[idx]

    monkeypatch.setattr(eval_mod, "evaluate_training_plan_soft", fake_soft_eval)

    report, _ = evaluate_training_plan_quality_file(
        str(plan_path),
        cfg=ConstraintConfig(min_signal_ids_per_day=0),
        soft_eval_cfg=SoftEvalConfig(enabled=True),
        soft_eval_runs=3,
    )

    soft = report["soft_assessment"]
    assert report["stats"]["inter_rater_runs"] == 3
    assert report["stats"]["inter_rater_consensus_method"]
    assert "goal_specificity" in report["stats"]["high_variance_markers"]
    assert soft["inter_rater_runs"] == 3
    assert soft["inter_rater_variance"]["goal_specificity"] > 0.5
    assert soft["summary"] == "run 2 summary"
    assert soft["confidence"] == "high"
    assert soft["marker_results"][0]["score"] == 3.0
    assert soft["marker_results"][0]["verdict"] == "partial"
    assert soft["rubric_scores"]["goal_alignment"]["score"] == 60.0
    assert soft["overall_score"] == 60.0
    assert soft["strengths"][0] == "Clear structure"
    assert "Goal-focused sessions" in soft["strengths"]
    assert "Clarify purpose" in soft["suggested_improvements"]
