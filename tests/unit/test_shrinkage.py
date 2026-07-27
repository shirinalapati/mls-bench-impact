from mls_bench_impact.models.shrinkage import reliability_weight, shrink_rate
from mls_bench_impact.models.positive_frequency import beta_binomial_adjust
from mls_bench_impact.scoring.bench_impact import PERIOD_FILTERS
from mls_bench_impact.scoring.confidence import classify_player, data_confidence
from mls_bench_impact.utils.time_utils import entry_timing_category, score_state_detailed, score_state_simple


def test_reliability_weight():
    assert abs(reliability_weight(450, 450) - 0.5) < 1e-9
    assert reliability_weight(0, 450) == 0


def test_shrink_rate():
    assert abs(shrink_rate(1.0, 0.0, 450, 450) - 0.5) < 1e-9


def test_beta_binomial():
    assert 0 < beta_binomial_adjust(3, 10) < 1


def test_entry_and_score_categories():
    assert entry_timing_category(20) == "emergency_early"
    assert entry_timing_category(70) == "standard"
    assert entry_timing_category(80) == "late"
    assert entry_timing_category(45, is_halftime=True) == "halftime"
    assert score_state_detailed(2) == "leading_by_two_plus"
    assert score_state_simple(-1) == "trailing"


def test_data_confidence_and_classification_invariants():
    assert data_confidence(5, 100, 0.9, 0.1, True) == "Insufficient"
    primary, tags = classify_player(
        {
            "bench_impact_score": 95,
            "substitute_sporting_impact": 80,
            "adjusted_team_impact_after_entry": 70,
            "data_confidence": "High",
            "substitute_appearances": 3,
            "substitute_minutes": 50,
            "components_missing": "",
        }
    )
    assert primary == "Small-Sample Watchlist"
    assert "Elite Game Changer" not in primary


def test_period_filters():
    assert PERIOD_FILTERS["2025-2026"]("2025")
    assert PERIOD_FILTERS["2026"]("2026")
    assert not PERIOD_FILTERS["2025"]("2026")