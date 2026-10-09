from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from app.database.session import get_db
from app.models.entities import Speaker, Statement, MonitoredSource
from app.models.schemas import SpeakerResponse, SpeakerCreate

router = APIRouter(prefix="/api/speakers", tags=["Speakers & Credibility"])

def _enrich_speaker_socials(sp: Speaker, db: Session) -> dict:
    socials = []
    
    # 1. Monitored sources linked to this speaker
    sources = db.query(MonitoredSource).filter(MonitoredSource.speaker_id == sp.id).all()
    for src in sources:
        if src.platform == "youtube":
            url = f"https://www.youtube.com/channel/{src.channel_identifier}" if not src.channel_identifier.startswith("http") else src.channel_identifier
            socials.append({
                "platform": "youtube",
                "identifier": src.channel_title or "YouTube",
                "url": url,
                "title": src.channel_title
            })
        elif src.platform == "telegram":
            socials.append({
                "platform": "telegram",
                "identifier": src.channel_identifier,
                "url": f"https://t.me/{src.channel_identifier.lstrip('@')}",
                "title": src.channel_title or "Telegram"
            })
        elif src.platform in ("twitter", "x"):
            handle = src.channel_identifier
            clean = handle.lstrip("@")
            socials.append({
                "platform": "x",
                "identifier": handle if handle.startswith("@") else f"@{handle}",
                "url": f"https://x.com/{clean}",
                "title": f"X: @{clean}"
            })

    # 2. Handle or channel property on speaker
    if sp.handle_or_channel:
        if sp.handle_or_channel.startswith("@"):
            clean = sp.handle_or_channel.lstrip("@")
            if not any(s["platform"] == "x" for s in socials):
                socials.append({
                    "platform": "x",
                    "identifier": sp.handle_or_channel,
                    "url": f"https://x.com/{clean}",
                    "title": f"X: {sp.handle_or_channel}"
                })
        elif "t.me" in sp.handle_or_channel:
            clean = sp.handle_or_channel.split("/")[-1]
            if not any(s["platform"] == "telegram" for s in socials):
                socials.append({
                    "platform": "telegram",
                    "identifier": f"@{clean}",
                    "url": f"https://t.me/{clean}",
                    "title": f"Telegram: @{clean}"
                })

    # 3. Fallback database for top crypto & tech personalities
    known_accounts = {
        "Michael Saylor": [
            {"platform": "x", "identifier": "@saylor", "url": "https://x.com/saylor", "title": "X: @saylor"},
            {"platform": "youtube", "identifier": "MicroStrategy", "url": "https://www.youtube.com/@MicroStrategy", "title": "YouTube: MicroStrategy"}
        ],
        "Vitalik Buterin": [
            {"platform": "x", "identifier": "@VitalikButerin", "url": "https://x.com/VitalikButerin", "title": "X: @VitalikButerin"},
            {"platform": "youtube", "identifier": "Ethereum Foundation", "url": "https://www.youtube.com/@EthereumFoundation", "title": "YouTube: Ethereum Foundation"}
        ],
        "Arthur Hayes": [
            {"platform": "x", "identifier": "@CryptoHayes", "url": "https://x.com/CryptoHayes", "title": "X: @CryptoHayes"},
            {"platform": "web", "identifier": "Maelstrom Substack", "url": "https://cryptohayes.substack.com", "title": "Substack"}
        ],
        "PlanB": [
            {"platform": "x", "identifier": "@100trillionUSD", "url": "https://x.com/100trillionUSD", "title": "X: @100trillionUSD"},
            {"platform": "youtube", "identifier": "PlanB", "url": "https://www.youtube.com/@100trillionUSD", "title": "YouTube: PlanB"}
        ],
        "Cathie Wood": [
            {"platform": "x", "identifier": "@CathieDWood", "url": "https://x.com/CathieDWood", "title": "X: @CathieDWood"},
            {"platform": "youtube", "identifier": "ARK Invest", "url": "https://www.youtube.com/@ARKInvest", "title": "YouTube: ARK Invest"}
        ],
        "Guy Turner (Coin Bureau)": [
            {"platform": "youtube", "identifier": "Coin Bureau (~2.5M)", "url": "https://www.youtube.com/@CoinBureau", "title": "YouTube: Coin Bureau"},
            {"platform": "x", "identifier": "@CoinBureau", "url": "https://x.com/CoinBureau", "title": "X: @CoinBureau"},
            {"platform": "telegram", "identifier": "@cbinsider", "url": "https://t.me/cbinsider", "title": "Telegram Insider"}
        ],
        "Benjamin Cowen": [
            {"platform": "youtube", "identifier": "Into The Cryptoverse", "url": "https://www.youtube.com/@BenjaminCowen", "title": "YouTube: Into The Cryptoverse"},
            {"platform": "x", "identifier": "@BenjaminCowen", "url": "https://x.com/BenjaminCowen", "title": "X: @BenjaminCowen"}
        ],
        "Raoul Pal": [
            {"platform": "youtube", "identifier": "Real Vision", "url": "https://www.youtube.com/@RealVisionFinance", "title": "YouTube: Real Vision"},
            {"platform": "x", "identifier": "@RaoulGMI", "url": "https://x.com/RaoulGMI", "title": "X: @RaoulGMI"}
        ],
        "Peter Schiff": [
            {"platform": "youtube", "identifier": "The Peter Schiff Show", "url": "https://www.youtube.com/@PeterSchiff", "title": "YouTube: Peter Schiff Show"},
            {"platform": "x", "identifier": "@PeterSchiff", "url": "https://x.com/PeterSchiff", "title": "X: @PeterSchiff"}
        ],
        "Altcoin Daily (Aaron & Austin)": [
            {"platform": "youtube", "identifier": "Altcoin Daily (~1.4M)", "url": "https://www.youtube.com/@AltcoinDaily", "title": "YouTube: Altcoin Daily"},
            {"platform": "x", "identifier": "@AltcoinDaily", "url": "https://x.com/AltcoinDaily", "title": "X: @AltcoinDaily"}
        ],
        "Elon Musk": [
            {"platform": "x", "identifier": "@elonmusk", "url": "https://x.com/elonmusk", "title": "X: @elonmusk"}
        ]
    }
    
    if sp.name in known_accounts:
        for acc in known_accounts[sp.name]:
            if not any(s["platform"] == acc["platform"] for s in socials):
                socials.append(acc)

    return {
        "id": sp.id,
        "name": sp.name,
        "handle_or_channel": sp.handle_or_channel,
        "bio": sp.bio,
        "avatar_url": sp.avatar_url,
        "overall_credibility": sp.overall_credibility,
        "overall_brier_score": sp.overall_brier_score,
        "total_predictions": sp.total_predictions,
        "resolved_predictions": sp.resolved_predictions,
        "correct_predictions": sp.correct_predictions,
        "domain_scores": sp.domain_scores or {},
        "created_at": sp.created_at,
        "social_accounts": socials
    }

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
        
    speakers = query.limit(limit).all()
    return [_enrich_speaker_socials(s, db) for s in speakers]

@router.get("/{speaker_id}", response_model=SpeakerResponse)
def get_speaker(speaker_id: str, db: Session = Depends(get_db)):
    speaker = db.query(Speaker).filter(Speaker.id == speaker_id).first()
    if not speaker:
        raise HTTPException(status_code=404, detail="Speaker not found")
    return _enrich_speaker_socials(speaker, db)

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
