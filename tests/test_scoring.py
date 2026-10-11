import pytest
from app.engine.scoring import ForecasterScorer

def test_brier_score_perfect():
    # Predicted 1.0, happened 1; predicted 0.0, didn't happen (outcome 0)
    history = [(1.0, 1), (0.0, 0)]
    score = ForecasterScorer.calculate_brier_score(history)
    assert score == 0.0

def test_brier_score_random_fifty_fifty():
    # Predicting 0.5 for all
    history = [(0.5, 1), (0.5, 0)]
    score = ForecasterScorer.calculate_brier_score(history)
    assert score == 0.25

def test_brier_score_worst():
    # Completely wrong every time with 100% confidence
    history = [(1.0, 0), (0.0, 1)]
    score = ForecasterScorer.calculate_brier_score(history)
    assert score == 1.0

def test_credibility_shrinkage():
    # A person with 0 predictions gets 0.5 default
    c0 = ForecasterScorer.brier_to_credibility(0.25, sample_size=0)
    assert c0 == 0.5
    
    # A person with 1 perfect prediction gets shrunken towards 0.5
    # raw is 0.95. shrinkage: (3 * 0.5 + 1 * 0.95) / 4 = 2.45 / 4 = 0.6125
    c1 = ForecasterScorer.brier_to_credibility(0.0, sample_size=1)
    assert 0.60 < c1 < 0.65
    
    # A person with 50 perfect predictions gets close to 0.95
    c50 = ForecasterScorer.brier_to_credibility(0.0, sample_size=50)
    assert c50 > 0.90
    
    # A terrible forecaster (BS = 0.6) after 50 samples gets low credibility
    c_bad = ForecasterScorer.brier_to_credibility(0.6, sample_size=50)
    assert c_bad < 0.2

def test_bayesian_aggregation_high_credibility():
    base_rate = 0.5
    # Reputable forecaster says 90% (weight 0.85)
    statements = [
        {"speaker_confidence": 0.9, "speaker_weight": 0.85}
    ]
    prob = ForecasterScorer.aggregate_event_probability(statements, base_rate)
    # Probability should shift significantly upwards
    assert prob > 0.80

def test_bayesian_aggregation_low_credibility_ignored():
    base_rate = 0.5
    # Clickbait blogger with weight 0.05 says 99%
    statements = [
        {"speaker_confidence": 0.99, "speaker_weight": 0.05}
    ]
    prob = ForecasterScorer.aggregate_event_probability(statements, base_rate)
    # Probability should barely move from 0.5
    assert 0.50 <= prob <= 0.56

def test_bayesian_aggregation_consensus():
    base_rate = 0.5
    # Two good forecasters agree it will happen
    statements = [
        {"speaker_confidence": 0.8, "speaker_weight": 0.8},
        {"speaker_confidence": 0.85, "speaker_weight": 0.75}
    ]
    prob = ForecasterScorer.aggregate_event_probability(statements, base_rate)
    assert prob > 0.85

def test_bayesian_aggregation_below_fifty_percent():
    # Skeptical forecasters and low prior base rate must produce probability well below 50%
    base_rate = 0.30
    statements = [
        {"speaker_confidence": 0.20, "speaker_weight": 0.75},
        {"speaker_confidence": 0.25, "speaker_weight": 0.65}
    ]
    prob = ForecasterScorer.aggregate_event_probability(statements, base_rate)
    assert prob < 0.15

