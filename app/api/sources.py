from typing import List, Dict, Any, Optional
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.database.session import get_db
from app.models.entities import MonitoredSource, Speaker
from app.ingestion.monitor import YouTubeChannelMonitor
from app.oracles.crypto_oracle import CryptoPriceOracle

router = APIRouter(prefix="/api/sources", tags=["Monitored Sources & Oracles"])

@router.get("")
def get_monitored_sources(db: Session = Depends(get_db)):
    sources = db.query(MonitoredSource).all()
    results = []
    for s in sources:
        sp = db.query(Speaker).filter(Speaker.id == s.speaker_id).first() if s.speaker_id else None
        results.append({
            "id": s.id,
            "speaker_id": s.speaker_id,
            "speaker_name": sp.name if sp else "None",
            "speaker_credibility": sp.overall_credibility if sp else 0.5,
            "platform": s.platform,
            "channel_title": s.channel_title,
            "channel_identifier": s.channel_identifier,
            "feed_url": s.feed_url,
            "last_scanned_at": s.last_scanned_at,
            "is_active": bool(s.is_active),
            "created_at": s.created_at
        })
    return results

@router.post("/{source_id}/scan")
async def scan_channel(source_id: str, db: Session = Depends(get_db)):
    res = await YouTubeChannelMonitor.scan_monitored_source(db, source_id)
    return res

@router.get("/oracle/prices")
async def get_live_prices():
    prices = await CryptoPriceOracle.get_live_prices()
    return prices

@router.post("/oracle/check")
async def check_crypto_events(auto_resolve: bool = False, db: Session = Depends(get_db)):
    evaluations = await CryptoPriceOracle.evaluate_active_crypto_events(db, auto_resolve=auto_resolve)
    return evaluations
