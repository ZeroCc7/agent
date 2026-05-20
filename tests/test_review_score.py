import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from app.types.models import ReviewScore

def test_overall_no_reference():
    score = ReviewScore(visual_quality=6.0, instruction_match=8.0, reference_match=None)
    assert abs(score.overall - (6.0 * 0.35 + 8.0 * 0.65)) < 0.01

def test_overall_with_reference():
    score = ReviewScore(visual_quality=6.0, instruction_match=8.0, reference_match=9.0)
    assert abs(score.overall - (6.0 * 0.25 + 8.0 * 0.40 + 9.0 * 0.35)) < 0.01

def test_is_satisfied_above_threshold():
    score = ReviewScore(visual_quality=9.0, instruction_match=9.0, reference_match=None)
    assert score.is_satisfied is True

def test_is_satisfied_below_threshold():
    score = ReviewScore(visual_quality=7.0, instruction_match=7.0, reference_match=None)
    assert score.is_satisfied is False
