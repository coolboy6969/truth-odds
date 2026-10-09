from typing import List, Optional, Dict, Any
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.database.session import get_db
from app.models.entities import Statement, Speaker, Event
from app.models.schemas import StatementCreate, StatementResponse, ExtractFromTextRequest
from app.services.prediction_service import PredictionService

router = APIRouter(prefix="/api/statements", tags=["Statements & Predictions"])

@router.get("", response_model=List[StatementResponse])
def get_statements(limit: int = 50, db: Session = Depends(get_db)):
    stmts = db.query(Statement).order_by(Statement.created_at.desc()).limit(limit).all()
    result = []
    for s in stmts:
        sp = db.query(Speaker).filter(Speaker.id == s.speaker_id).first()
        result.append({
            "id": s.id,
            "speaker_id": s.speaker_id,
            "speaker_name": sp.name if sp else "Unknown",
            "speaker_credibility": sp.overall_credibility if sp else 0.5,
            "event_id": s.event_id,
            "source_platform": s.source_platform,
            "source_url": s.source_url,
            "raw_quote": s.raw_quote,
            "speaker_confidence": s.speaker_confidence,
            "speaker_weight_applied": s.speaker_weight_applied,
            "created_at": s.created_at
        })
    return result

@router.post("", response_model=StatementResponse)
def create_statement(payload: StatementCreate, db: Session = Depends(get_db)):
    event_title = payload.event_title
    if not event_title and payload.event_id:
        ev = db.query(Event).filter(Event.id == payload.event_id).first()
        if ev:
            event_title = ev.title
            
    if not event_title:
        raise HTTPException(status_code=400, detail="Either event_id or event_title must be provided")

    stmt = PredictionService.record_statement(
        db=db,
        speaker_name=payload.speaker_name,
        speaker_handle=payload.speaker_handle,
        event_title=event_title,
        event_domain=payload.event_domain,
        speaker_confidence=payload.speaker_confidence,
        raw_quote=payload.raw_quote,
        source_url=payload.source_url,
        source_platform=payload.source_platform
    )
    
    sp = db.query(Speaker).filter(Speaker.id == stmt.speaker_id).first()
    return {
        "id": stmt.id,
        "speaker_id": stmt.speaker_id,
        "speaker_name": sp.name if sp else payload.speaker_name,
        "speaker_credibility": sp.overall_credibility if sp else 0.5,
        "event_id": stmt.event_id,
        "source_platform": stmt.source_platform,
        "source_url": stmt.source_url,
        "raw_quote": stmt.raw_quote,
        "speaker_confidence": stmt.speaker_confidence,
        "speaker_weight_applied": stmt.speaker_weight_applied,
        "created_at": stmt.created_at
    }

@router.post("/ingest")
async def ingest_media_or_text(payload: ExtractFromTextRequest, db: Session = Depends(get_db)):
    """
    Ingests text or YouTube video URL, extracts claims, and updates event probabilities.
    """
    result = await PredictionService.process_media_or_text(
        db=db,
        text_or_url=payload.text,
        speaker_name=payload.speaker_name,
        source_platform=payload.source_platform
    )
    return result
