from datetime import datetime
from typing import Dict, Any, List, Tuple
from sqlalchemy.orm import Session
from app.models.entities import Event, Statement, Speaker
from app.engine.scoring import ForecasterScorer

class ResolutionEngine:
    """
    Handles event resolution (Oracles) and triggers automatic recalculation
    of forecaster accuracy (Brier score, domain calibration, and credibility).
    """

    @classmethod
    def resolve_event(
        cls,
        db: Session,
        event_id: str,
        outcome: bool,
        resolution_notes: str = ""
    ) -> Event:
        """
        Resolves an event as TRUE (1) or FALSE (0), updates event status,
        and recalculates the track record of every forecaster who made a statement on it.
        """
        event = db.query(Event).filter(Event.id == event_id).first()
        if not event:
            raise ValueError(f"Event {event_id} not found")
        
        event.status = "RESOLVED_TRUE" if outcome else "RESOLVED_FALSE"
        event.resolved_at = datetime.utcnow()
        event.resolution_notes = resolution_notes
        # Final probability for resolved event is 1.0 or 0.0
        event.current_probability = 1.0 if outcome else 0.0
        
        # Get all speakers who made statements on this event
        statements = db.query(Statement).filter(Statement.event_id == event_id).all()
        speaker_ids = list({s.speaker_id for s in statements})
        
        db.commit()
        db.refresh(event)
        
        # Recalculate each speaker's metrics
        for sp_id in speaker_ids:
            cls.recalculate_speaker_track_record(db, sp_id)
            
        return event

    @classmethod
    def recalculate_speaker_track_record(cls, db: Session, speaker_id: str) -> Speaker:
        """
        Recomputes overall and domain-specific Brier scores, hit rates,
        and credibility weights across all resolved events for a speaker.
        """
        speaker = db.query(Speaker).filter(Speaker.id == speaker_id).first()
        if not speaker:
            raise ValueError(f"Speaker {speaker_id} not found")
            
        # Find all statements by this speaker
        statements = db.query(Statement).filter(Statement.speaker_id == speaker_id).all()
        speaker.total_predictions = len(statements)
        
        # Collect resolved predictions: list of (confidence, actual_outcome_binary, domain)
        resolved_records: List[Tuple[float, int, str]] = []
        
        for stmt in statements:
            ev = db.query(Event).filter(Event.id == stmt.event_id).first()
            if ev and ev.status in ("RESOLVED_TRUE", "RESOLVED_FALSE"):
                actual = 1 if ev.status == "RESOLVED_TRUE" else 0
                resolved_records.append((stmt.speaker_confidence, actual, ev.domain))
                
        speaker.resolved_predictions = len(resolved_records)
        
        if not resolved_records:
            # No resolved events yet - keep defaults
            speaker.overall_brier_score = 0.25
            speaker.overall_credibility = 0.5
            speaker.correct_predictions = 0
            db.commit()
            db.refresh(speaker)
            return speaker
            
        # Overall calculations
        overall_pairs = [(prob, outcome) for prob, outcome, _ in resolved_records]
        brier = ForecasterScorer.calculate_brier_score(overall_pairs)
        cred = ForecasterScorer.brier_to_credibility(brier, sample_size=len(overall_pairs))
        hit_rate = ForecasterScorer.calculate_hit_rate(overall_pairs)
        
        speaker.overall_brier_score = round(brier, 4)
        speaker.overall_credibility = round(cred, 4)
        speaker.correct_predictions = int(hit_rate * len(overall_pairs))
        
        # Domain-specific breakdowns
        domain_groups: Dict[str, List[Tuple[float, int]]] = {}
        for prob, outcome, domain in resolved_records:
            domain_key = domain.lower().strip() if domain else "general"
            domain_groups.setdefault(domain_key, []).append((prob, outcome))
            
        domain_scores: Dict[str, Any] = {}
        for d_key, pairs in domain_groups.items():
            d_brier = ForecasterScorer.calculate_brier_score(pairs)
            d_cred = ForecasterScorer.brier_to_credibility(d_brier, sample_size=len(pairs))
            d_hits = ForecasterScorer.calculate_hit_rate(pairs)
            
            domain_scores[d_key] = {
                "brier_score": round(d_brier, 4),
                "credibility": round(d_cred, 4),
                "sample_size": len(pairs),
                "correct": int(d_hits * len(pairs)),
                "hit_rate_pct": round(d_hits * 100, 1)
            }
            
        speaker.domain_scores = domain_scores
        
        db.commit()
        db.refresh(speaker)
        return speaker
