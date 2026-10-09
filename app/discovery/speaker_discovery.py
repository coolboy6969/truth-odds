import re
from typing import List, Dict, Any, Optional
from sqlalchemy.orm import Session
from app.models.entities import DiscoveredSpeakerCandidate, Speaker
from app.services.prediction_service import PredictionService

class SpeakerDiscoveryEngine:
    """
    Discovers new opinion leaders and forecasting personalities by analyzing
    co-occurrence networks, guest mentions, and interviews across social channels.
    """

    GUEST_PATTERNS = [
        # English patterns
        r'(?:interview with|talking to|discussion with|featuring|guest:?)\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+){1,2})',
        r'([A-Z][a-z]+(?:\s+[A-Z][a-z]+){1,2})\s+(?:predicts|warns|explains|reveals|forecasts|drops truth)',
        r'(?:ft\.|feat\.|with)\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+){1,2})',
        # Russian patterns
        r'(?:интервью с|в гостях у нас|беседа с|прогноз от)\s+([А-ЯЁ][а-яё]+(?:\s+[А-ЯЁ][а-яё]+){1,2})',
        r'([А-ЯЁ][а-яё]+(?:\s+[А-ЯЁ][а-яё]+){1,2})\s+(?:прогнозирует|предупреждает|объясняет|дал прогноз)'
    ]

    EXCLUDE_KEYWORDS = {
        "bitcoin", "crypto", "ethereum", "altcoin", "market", "bull", "bear",
        "биткоин", "эфириум", "крипта", "рынок", "бычий", "медвежий", "сегодня", "новость"
    }

    @classmethod
    def extract_potential_speakers(cls, text_or_title: str) -> List[str]:
        found_names = set()
        for pattern in cls.GUEST_PATTERNS:
            matches = re.finditer(pattern, text_or_title, re.IGNORECASE)
            for m in matches:
                name = m.group(1).strip()
                # Filter out obvious false positives
                name_words = name.lower().split()
                if any(w in cls.EXCLUDE_KEYWORDS for w in name_words):
                    continue
                if 4 <= len(name) <= 35 and len(name.split()) in (2, 3):
                    # Title case format
                    formatted_name = " ".join(w.capitalize() for w in name.split())
                    found_names.add(formatted_name)
        return list(found_names)

    @classmethod
    def register_or_update_candidate(
        cls,
        db: Session,
        name: str,
        channel_title: str,
        context_quote: str = "",
        contains_claim: bool = True
    ) -> DiscoveredSpeakerCandidate:
        name_clean = name.strip()
        
        # Check if already a full speaker
        existing_speaker = db.query(Speaker).filter(Speaker.name.ilike(name_clean)).first()
        if existing_speaker:
            return None

        # Check existing candidate
        candidate = db.query(DiscoveredSpeakerCandidate).filter(
            DiscoveredSpeakerCandidate.name.ilike(name_clean)
        ).first()

        if candidate:
            candidate.mention_count += 1
            if contains_claim:
                candidate.claim_density_score = min(1.0, candidate.claim_density_score + 0.15)
            if context_quote:
                candidate.context_quote = context_quote[:300]
        else:
            candidate = DiscoveredSpeakerCandidate(
                name=name_clean,
                discovered_via_channel=channel_title,
                context_quote=context_quote[:300] if context_quote else f"Обнаружен в контенте канала {channel_title}",
                mention_count=1,
                claim_density_score=0.65 if contains_claim else 0.40,
                status="CANDIDATE"
            )
            db.add(candidate)

        # Check for auto-promotion threshold: mentioned on multiple channels with good claim density
        if candidate.mention_count >= 2 and candidate.claim_density_score >= 0.60 and candidate.status == "CANDIDATE":
            cls.promote_candidate_to_speaker(db, candidate.id)

        db.commit()
        db.refresh(candidate)
        return candidate

    @classmethod
    def promote_candidate_to_speaker(cls, db: Session, candidate_id: str) -> Optional[Speaker]:
        candidate = db.query(DiscoveredSpeakerCandidate).filter(
            DiscoveredSpeakerCandidate.id == candidate_id
        ).first()
        if not candidate:
            return None

        speaker = PredictionService.get_or_create_speaker(
            db=db,
            name=candidate.name,
            handle_or_channel=f"Discovered via {candidate.discovered_via_channel}"
        )
        speaker.bio = f"Обнаружен автоматически через анализ контента ({candidate.mention_count} упоминаний)"
        
        candidate.status = "APPROVED"
        db.commit()
        db.refresh(speaker)
        return speaker
