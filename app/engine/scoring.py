import math
from typing import List, Tuple, Dict, Any, Optional

class ForecasterScorer:
    """
    Mathematical engine for computing forecaster credibility, Brier scores,
    and Bayesian log-odds aggregation for event probabilities.
    """

    @staticmethod
    def calculate_brier_score(predictions_and_outcomes: List[Tuple[float, int]]) -> float:
        """
        Calculates the Brier Score: Mean Squared Error of probabilistic predictions.
        BS = (1/N) * sum((f_i - o_i)^2)
        - f_i: predicted probability in [0, 1]
        - o_i: actual binary outcome (1 for happened, 0 for did not happen)
        
        Range: [0.0, 1.0]. 0.0 is perfect, 0.25 is random guessing (coin flip).
        """
        if not predictions_and_outcomes:
            return 0.25  # Prior default (equivalent to 50/50 guessing)
        
        total_sq_error = sum((prob - outcome) ** 2 for prob, outcome in predictions_and_outcomes)
        return total_sq_error / len(predictions_and_outcomes)

    @staticmethod
    def calculate_hit_rate(predictions_and_outcomes: List[Tuple[float, int]]) -> float:
        """
        Computes the simple directional hit rate / accuracy.
        A prediction is considered a 'hit' if:
        - prob >= 0.5 and outcome == 1
        - prob < 0.5 and outcome == 0
        """
        if not predictions_and_outcomes:
            return 0.5
        
        hits = sum(1 for prob, outcome in predictions_and_outcomes if (prob >= 0.5 and outcome == 1) or (prob < 0.5 and outcome == 0))
        return hits / len(predictions_and_outcomes)

    @staticmethod
    def brier_to_credibility(
        brier_score: float, 
        sample_size: int, 
        prior_weight: float = 0.5, 
        prior_samples: int = 3
    ) -> float:
        """
        Maps a Brier Score to a credibility score [0.05, 0.95] with Bayesian shrinkage.
        
        - Perfect forecaster (BS = 0.0): Raw credibility -> 1.0
        - Baseline 50/50 forecaster (BS = 0.25): Raw credibility -> 0.5
        - Antitrader/Inverse signal (BS = 0.5+): Raw credibility -> < 0.25
        
        Shrinkage formula: (prior_samples * prior_weight + sample_size * raw_cred) / (prior_samples + sample_size)
        Prevents forecasters with 1 lucky prediction from getting an undeserved 100% weight.
        """
        # Brier Skill Score relative to 0.25 reference
        # BSS = 1 - (BS / 0.25)
        # BSS = 1 (BS=0), BSS = 0 (BS=0.25), BSS = -1 (BS=0.5)
        bss = 1.0 - (brier_score / 0.25)
        
        # Raw credibility scaled to [0.05, 0.95]
        # raw = 0.5 + 0.5 * bss
        raw_credibility = 0.5 + (0.45 * bss)
        raw_credibility = max(0.05, min(0.95, raw_credibility))
        
        # Bayesian shrinkage against default prior
        weighted_credibility = (
            (prior_samples * prior_weight) + (sample_size * raw_credibility)
        ) / (prior_samples + sample_size)
        
        return round(weighted_credibility, 4)

    @staticmethod
    def prob_to_log_odds(p: float, epsilon: float = 1e-4) -> float:
        """Converts probability in [0, 1] to log-odds (logit). Clamped for numerical stability."""
        p_clamped = max(epsilon, min(1.0 - epsilon, p))
        return math.log(p_clamped / (1.0 - p_clamped))

    @staticmethod
    def log_odds_to_prob(log_odds: float) -> float:
        """Converts log-odds (logit) back to probability in [0, 1]."""
        # Prevent overflow in exp
        if log_odds > 35:
            return 0.9999
        if log_odds < -35:
            return 0.0001
        return 1.0 / (1.0 + math.exp(-log_odds))

    @classmethod
    def aggregate_event_probability(
        cls,
        statements: List[Dict[str, Any]],
        base_rate: float = 0.5
    ) -> float:
        """
        Aggregates multiple forecaster statements into a single posterior event probability
        using weighted Bayesian Log-Odds aggregation.
        
        Formula:
          L_posterior = L_base + sum( w_i * (L_i - L_base) )
        
        where:
          - L_base is prior log-odds of event
          - w_i is speaker's credibility weight in this domain [0.05, 0.95]
          - L_i is the log-odds corresponding to speaker's forecast
        """
        if not statements:
            return base_rate
        
        l_base = cls.prob_to_log_odds(base_rate)
        l_posterior = l_base
        
        for stmt in statements:
            speaker_confidence = stmt.get("speaker_confidence", 0.5)
            weight = stmt.get("speaker_weight", 0.5)
            
            # Speaker's log-likelihood ratio relative to neutral 50% (logit(0.5) = 0):
            # > 0 when confidence > 50%, < 0 when confidence < 50%
            l_speaker = cls.prob_to_log_odds(speaker_confidence)
            l_posterior += weight * l_speaker
            
        prob = cls.log_odds_to_prob(l_posterior)
        return round(prob, 4)
