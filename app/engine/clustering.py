import re
from typing import Optional, List, Tuple
from sqlalchemy.orm import Session
from app.models.entities import Event

class SemanticEventMatcher:
    """
    Matches incoming prediction claims to existing active events to avoid duplicates.
    Example:
      'BTC достигнет 150к к концу 2026' and 'Биткоин преодолеет $150,000 до конца 2026 года'
      should be resolved to the exact same Event.
    """

    @classmethod
    def find_matching_event(cls, db: Session, hypothesis: str, domain: str = "crypto") -> Optional[Event]:
        active_events = db.query(Event).filter(
            Event.status == "ACTIVE",
            Event.domain.ilike(domain)
        ).all()
        
        if not active_events:
            return None

        # Normalized tokens from incoming hypothesis
        target_tokens = cls._tokenize_and_normalize(hypothesis)
        if not target_tokens:
            return None

        best_match = None
        highest_similarity = 0.0

        from app.engine.auto_analysis import AutoEventAnalysisEngine
        target_is_bearish = AutoEventAnalysisEngine.is_bearish_or_negated_claim(hypothesis)

        for ev in active_events:
            ev_is_bearish = AutoEventAnalysisEngine.is_bearish_or_negated_claim(ev.title)
            if target_is_bearish != ev_is_bearish:
                continue

            ev_tokens = cls._tokenize_and_normalize(ev.title)
            similarity = cls._calculate_jaccard_similarity(target_tokens, ev_tokens)
            
            # Additional boost if key numerical milestones match (e.g. 150000, 150k, 100k)
            num_boost = cls._compare_numeric_targets(hypothesis, ev.title)
            total_score = similarity + num_boost

            if total_score > highest_similarity:
                highest_similarity = total_score
                best_match = ev

        # Threshold for accepting match
        if highest_similarity >= 0.45:
            return best_match
            
        return None

    @staticmethod
    def _normalize_numbers(text: str) -> str:
        t = text.lower()
        t = t.replace("150,000", "150k").replace("150 000", "150k").replace("150000", "150k").replace("150к", "150k")
        t = t.replace("100,000", "100k").replace("100 000", "100k").replace("100000", "100k").replace("100к", "100k")
        t = t.replace("200,000", "200k").replace("200 000", "200k").replace("200000", "200k").replace("200к", "200k")
        t = t.replace("250,000", "250k").replace("250 000", "250k").replace("250000", "250k").replace("250к", "250k")
        t = t.replace("1,000,000", "1m").replace("1 000 000", "1m").replace("1000000", "1m").replace("1м", "1m").replace("1млн", "1m")
        return t

    @classmethod
    def _tokenize_and_normalize(cls, text: str) -> set:
        text = cls._normalize_numbers(text)
        # Synonyms normalization
        text = text.replace("bitcoin", "btc").replace("биткоин", "btc").replace("биткоина", "btc").replace("биткойн", "btc")
        text = text.replace("ethereum", "eth").replace("эфириум", "eth").replace("эфир", "eth")
        
        words = re.findall(r'\b[a-zA-Zа-яА-Я0-9_]{2,}\b', text)
        stopwords = {"достигнет", "превысит", "пробьет", "будет", "года", "году", "концу", "перед", "после", "year", "reach", "above", "до", "на", "за", "из", "от", "по"}
        return {w for w in words if w not in stopwords}

    @staticmethod
    def _calculate_jaccard_similarity(tokens1: set, tokens2: set) -> float:
        if not tokens1 or not tokens2:
            return 0.0
        intersection = len(tokens1.intersection(tokens2))
        union = len(tokens1.union(tokens2))
        return intersection / union

    @classmethod
    def _compare_numeric_targets(cls, text1: str, text2: str) -> float:
        t1 = cls._normalize_numbers(text1)
        t2 = cls._normalize_numbers(text2)
        years = {str(y) for y in range(2015, 2040)}
        nums1 = set(re.findall(r'\b\d+(?:k|m|к|м)?\b', t1)) - years
        nums2 = set(re.findall(r'\b\d+(?:k|m|к|м)?\b', t2)) - years
        if nums1 and nums2:
            if nums1.intersection(nums2):
                return 0.35  # Strong boost when non-year price targets match
            return -0.50     # Different numeric targets must not merge
        return 0.0
