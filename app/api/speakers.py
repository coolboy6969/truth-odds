from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from app.database.session import get_db
from app.models.entities import Speaker, Statement
from app.models.schemas import SpeakerResponse, SpeakerCreate

router = APIRouter(prefix="/api/speakers", tags=["Speakers & Credibility"])

@router.get("", response_model=List[SpeakerResponse])
def get_speakers(
    sort_by: str = Query("credibility", enum=["credibility", "brier", "predictions", "name"]),
    limit: int = 50,
    db: Session = Depends(get_db)
):
    query = db.query(Speaker)
    if sort_by == "credibility":
        query = query.order_by(Speaker.overall_credibility.desc())
    elif sort_by == "brier":
        query = query.order_by(Speaker.overall_brier_score.asc())
    elif sort_by == "predictions":
        query = query.order_by(Speaker.total_predictions.desc())
    else:
        query = query.order_by(Speaker.name.asc())
        
    return query.limit(limit).all()

@router.get("/{speaker_id}", response_model=SpeakerResponse)
def get_speaker(speaker_id: str, db: Session = Depends(get_db)):
    speaker = db.query(Speaker).filter(Speaker.id == speaker_id).first()
    if not speaker:
        raise HTTPException(status_code=404, detail="Speaker not found")
    return speaker

@router.post("", response_model=SpeakerResponse)
def create_speaker(payload: SpeakerCreate, db: Session = Depends(get_db)):
    existing = db.query(Speaker).filter(Speaker.name.ilike(payload.name.strip())).first()
    if existing:
        return existing
        
    sp = Speaker(
        name=payload.name.strip(),
        handle_or_channel=payload.handle_or_channel,
        bio=payload.bio,
        avatar_url=payload.avatar_url,
        overall_credibility=0.5,
        overall_brier_score=0.25,
        domain_scores={}
    )
    db.add(sp)
    db.commit()
    db.refresh(sp)
    return sp
