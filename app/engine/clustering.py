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

        for ev in active_events:
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
    def _tokenize_and_normalize(text: str) -> set:
        text = text.lower()
        # Synonyms normalization
        text = text.replace("bitcoin", "btc").replace("биткоин", "btc").replace("биткоина", "btc")
        text = text.replace("ethereum", "eth").replace("эфириум", "eth").replace("эфир", "eth")
        text = text.replace("150,000", "150k").replace("150000", "150k").replace("150к", "150k")
        text = text.replace("100,000", "100k").replace("100000", "100k").replace("100к", "100k")
        text = text.replace("200,000", "200k").replace("200000", "200k").replace("200к", "200k")
        text = text.replace("1,000,000", "1m").replace("1000000", "1m").replace("1м", "1m").replace("1млн", "1m")
        
        words = re.findall(r'\b[a-zA-Zа-яА-Я0-9_]{3,}\b', text)
        stopwords = {"достигнет", "превысит", "пробьет", "будет", "года", "концу", "перед", "после", "year", "reach", "above"}
        return {w for w in words if w not in stopwords}

    @staticmethod
    def _calculate_jaccard_similarity(tokens1: set, tokens2: set) -> float:
        if not tokens1 or not tokens2:
            return 0.0
        intersection = len(tokens1.intersection(tokens2))
        union = len(tokens1.union(tokens2))
        return intersection / union

    @staticmethod
    def _compare_numeric_targets(text1: str, text2: str) -> float:
        nums1 = set(re.findall(r'\b\d+(?:k|m|к|м)?\b', text1.lower()))
        nums2 = set(re.findall(r'\b\d+(?:k|m|к|м)?\b', text2.lower()))
        if nums1 and nums2 and nums1.intersection(nums2):
            return 0.35  # Strong boost when price targets match
        return 0.0
