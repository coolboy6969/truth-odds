from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from app.database.session import get_db
from app.models.entities import Event, Statement, Speaker
from app.models.schemas import EventResponse, EventCreate, EventResolveRequest, StatementResponse
from app.engine.resolution import ResolutionEngine

router = APIRouter(prefix="/api/events", tags=["Events & Probabilities"])

@router.get("", response_model=List[EventResponse])
def get_events(
    domain: Optional[str] = None,
    status: Optional[str] = None,
    db: Session = Depends(get_db)
):
    query = db.query(Event)
    if domain:
        query = query.filter(Event.domain.ilike(domain))
    if status:
        query = query.filter(Event.status == status)
    
    events = query.order_by(Event.created_at.desc()).all()
    
    # Enrich statements with speaker names for response
    result = []
    for ev in events:
        ev_dict = {
            "id": ev.id,
            "title": ev.title,
            "description": ev.description,
            "domain": ev.domain,
            "base_rate": ev.base_rate,
            "current_probability": ev.current_probability,
            "deadline": ev.deadline,
            "status": ev.status,
            "resolution_notes": ev.resolution_notes,
            "resolved_at": ev.resolved_at,
            "created_at": ev.created_at,
            "statements": []
        }
        for st in ev.statements:
            sp = db.query(Speaker).filter(Speaker.id == st.speaker_id).first()
            ev_dict["statements"].append({
                "id": st.id,
                "speaker_id": st.speaker_id,
                "speaker_name": sp.name if sp else "Unknown",
                "speaker_credibility": sp.overall_credibility if sp else 0.5,
                "event_id": st.event_id,
                "source_platform": st.source_platform,
                "source_url": st.source_url,
                "raw_quote": st.raw_quote,
                "speaker_confidence": st.speaker_confidence,
                "speaker_weight_applied": st.speaker_weight_applied,
                "created_at": st.created_at
            })
        result.append(ev_dict)
    return result

@router.get("/{event_id}", response_model=EventResponse)
def get_event(event_id: str, db: Session = Depends(get_db)):
    ev = db.query(Event).filter(Event.id == event_id).first()
    if not ev:
        raise HTTPException(status_code=404, detail="Event not found")
        
    stmts = []
    for st in ev.statements:
        sp = db.query(Speaker).filter(Speaker.id == st.speaker_id).first()
        stmts.append({
            "id": st.id,
            "speaker_id": st.speaker_id,
            "speaker_name": sp.name if sp else "Unknown",
            "speaker_credibility": sp.overall_credibility if sp else 0.5,
            "event_id": st.event_id,
            "source_platform": st.source_platform,
            "source_url": st.source_url,
            "raw_quote": st.raw_quote,
            "speaker_confidence": st.speaker_confidence,
            "speaker_weight_applied": st.speaker_weight_applied,
            "created_at": st.created_at
        })
        
    return {
        "id": ev.id,
        "title": ev.title,
        "description": ev.description,
        "domain": ev.domain,
        "base_rate": ev.base_rate,
        "current_probability": ev.current_probability,
        "deadline": ev.deadline,
        "status": ev.status,
        "resolution_notes": ev.resolution_notes,
        "resolved_at": ev.resolved_at,
        "created_at": ev.created_at,
        "statements": stmts
    }

@router.post("", response_model=EventResponse)
def create_event(payload: EventCreate, db: Session = Depends(get_db)):
    from app.engine.auto_analysis import AutoEventAnalysisEngine

    ev = Event(
        title=payload.title.strip(),
        description=payload.description,
        domain=payload.domain.lower(),
        base_rate=payload.base_rate,
        current_probability=payload.base_rate,
        deadline=payload.deadline,
        status="ACTIVE"
    )
    db.add(ev)
    db.commit()
    db.refresh(ev)

    if payload.auto_analyze:
        ev = AutoEventAnalysisEngine.analyze_and_forecast_event(
            db=db,
            event=ev,
            speaker_name=payload.speaker_name,
            speaker_confidence=payload.speaker_confidence
        )
        from app.oracles.auto_oracle import AutoOracleService
        AutoOracleService.check_all_active_events(db=db, auto_resolve=False)

    stmts = []
    for st in ev.statements:
        sp = db.query(Speaker).filter(Speaker.id == st.speaker_id).first()
        stmts.append({
            "id": st.id,
            "speaker_id": st.speaker_id,
            "speaker_name": sp.name if sp else "Unknown",
            "speaker_credibility": sp.overall_credibility if sp else 0.5,
            "event_id": st.event_id,
            "source_platform": st.source_platform,
            "source_url": st.source_url,
            "raw_quote": st.raw_quote,
            "speaker_confidence": st.speaker_confidence,
            "speaker_weight_applied": st.speaker_weight_applied,
            "created_at": st.created_at
        })

    return {
        "id": ev.id,
        "title": ev.title,
        "description": ev.description,
        "domain": ev.domain,
        "base_rate": ev.base_rate,
        "current_probability": ev.current_probability,
        "deadline": ev.deadline,
        "status": ev.status,
        "resolution_notes": ev.resolution_notes,
        "resolved_at": ev.resolved_at,
        "created_at": ev.created_at,
        "statements": stmts
    }

@router.post("/{event_id}/resolve", response_model=EventResponse)
def resolve_event(
    event_id: str,
    payload: EventResolveRequest,
    db: Session = Depends(get_db)
):
    try:
        resolved = ResolutionEngine.resolve_event(
            db=db,
            event_id=event_id,
            outcome=payload.outcome,
            resolution_notes=payload.resolution_notes or ""
        )
        return resolved
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))

@router.delete("/{event_id}")
def delete_event(event_id: str, db: Session = Depends(get_db)):
    ev = db.query(Event).filter(Event.id == event_id).first()
    if not ev:
        raise HTTPException(status_code=404, detail="Event not found")
    
    # Delete associated statements
    db.query(Statement).filter(Statement.event_id == event_id).delete()
    db.delete(ev)
    db.commit()
    return {"success": True, "message": f"Событие «{ev.title}» успешно удалено"}
