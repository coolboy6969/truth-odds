from typing import Dict, Any, List, Optional
from sqlalchemy.orm import Session
from app.models.entities import Speaker, Event, Statement
from app.engine.scoring import ForecasterScorer
from app.extractor.llm_extractor import LLMPredictionExtractor
from app.ingestion.youtube import YouTubeIngestionService

class PredictionService:
    """
    High-level business service connecting ingestion, extraction,
    speaker weight retrieval, statement recording, and event probability recalculation.
    """

    @classmethod
    def get_or_create_speaker(cls, db: Session, name: str, handle_or_channel: Optional[str] = None) -> Speaker:
        name_clean = name.strip()
        speaker = db.query(Speaker).filter(Speaker.name.ilike(name_clean)).first()
        if not speaker:
            speaker = Speaker(
                name=name_clean,
                handle_or_channel=handle_or_channel,
                overall_credibility=0.5,
                overall_brier_score=0.25,
                total_predictions=0,
                resolved_predictions=0,
                correct_predictions=0,
                domain_scores={}
            )
            db.add(speaker)
            db.commit()
            db.refresh(speaker)
        return speaker

    @classmethod
    def get_or_create_event(cls, db: Session, title: str, domain: str = "general", base_rate: float = 0.5) -> Event:
        title_clean = title.strip()
        # Find existing event by close title match or create new
        event = db.query(Event).filter(Event.title.ilike(title_clean)).first()
        if not event:
            event = Event(
                title=title_clean,
                domain=domain.lower(),
                base_rate=base_rate,
                current_probability=base_rate,
                status="ACTIVE"
            )
            db.add(event)
            db.commit()
            db.refresh(event)
        return event

    @classmethod
    def get_speaker_weight_for_domain(cls, speaker: Speaker, domain: str) -> float:
        domain_key = domain.lower() if domain else "general"
        domain_scores = speaker.domain_scores or {}
        if domain_key in domain_scores and "credibility" in domain_scores[domain_key]:
            return float(domain_scores[domain_key]["credibility"])
        return float(speaker.overall_credibility or 0.5)

    @classmethod
    def record_statement(
        cls,
        db: Session,
        speaker_name: str,
        event_title: str,
        speaker_confidence: float,
        raw_quote: str,
        source_url: str,
        source_platform: str = "youtube",
        event_domain: str = "general",
        speaker_handle: Optional[str] = None,
        base_rate: float = 0.5
    ) -> Statement:
        speaker = cls.get_or_create_speaker(db, speaker_name, speaker_handle)
        event = cls.get_or_create_event(db, event_title, event_domain, base_rate)
        
        # Get speaker's domain weight
        weight = cls.get_speaker_weight_for_domain(speaker, event.domain)
        
        statement = Statement(
            speaker_id=speaker.id,
            event_id=event.id,
            source_platform=source_platform,
            source_url=source_url,
            raw_quote=raw_quote,
            speaker_confidence=speaker_confidence,
            speaker_weight_applied=weight
        )
        db.add(statement)
        db.commit()
        db.refresh(statement)
        
        # Recalculate event's aggregated probability based on all statements
        all_event_statements = db.query(Statement).filter(Statement.event_id == event.id).all()
        
        stmt_dicts = []
        for s in all_event_statements:
            sp = db.query(Speaker).filter(Speaker.id == s.speaker_id).first()
            sp_weight = cls.get_speaker_weight_for_domain(sp, event.domain) if sp else s.speaker_weight_applied
            stmt_dicts.append({
                "speaker_confidence": s.speaker_confidence,
                "speaker_weight": sp_weight
            })
            
        new_prob = ForecasterScorer.aggregate_event_probability(stmt_dicts, event.base_rate)
        event.current_probability = new_prob
        db.commit()
        db.refresh(event)
        
        return statement

    @classmethod
    async def process_media_or_text(
        cls,
        db: Session,
        text_or_url: str,
        speaker_name: Optional[str] = None,
        source_platform: str = "youtube"
    ) -> Dict[str, Any]:
        """
        Parses text or fetches YouTube transcript, extracts all predictions,
        and records them into the system.
        """
        raw_text = text_or_url
        source_url = text_or_url
        
        # Check if text_or_url is a YouTube link
        if "youtube.com" in text_or_url or "youtu.be" in text_or_url:
            yt_res = YouTubeIngestionService.get_transcript(text_or_url)
            if yt_res.get("success"):
                raw_text = yt_res.get("full_text", "")
            else:
                return {
                    "success": False,
                    "error": f"Failed to get YouTube transcript: {yt_res.get('error')}",
                    "predictions": []
                }
                
        # Run extractor
        extracted = await LLMPredictionExtractor.extract_predictions(raw_text, speaker_name)
        
        recorded_statements = []
        for p in extracted:
            s_name = p.get("speaker_name") or speaker_name or "Unknown Speaker"
            stmt = cls.record_statement(
                db=db,
                speaker_name=s_name,
                event_title=p.get("event_hypothesis", "Unspecified event"),
                speaker_confidence=float(p.get("speaker_confidence", 0.5)),
                raw_quote=p.get("raw_quote", raw_text[:200]),
                source_url=source_url,
                source_platform=source_platform,
                event_domain=p.get("domain", "general")
            )
            recorded_statements.append({
                "statement_id": stmt.id,
                "speaker": s_name,
                "event": p.get("event_hypothesis"),
                "confidence": p.get("speaker_confidence"),
                "applied_weight": stmt.speaker_weight_applied
            })
            
        return {
            "success": True,
            "count": len(recorded_statements),
            "recorded": recorded_statements
        }
