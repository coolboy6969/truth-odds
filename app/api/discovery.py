from typing import List, Dict, Any, Optional
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session
from app.database.session import get_db
from app.models.entities import DiscoveredSpeakerCandidate, NarrativeCluster, Speaker
from app.discovery.speaker_discovery import SpeakerDiscoveryEngine, is_valid_analyst_name, normalize_analyst_url
from app.discovery.event_discovery import EventDiscoveryEngine

router = APIRouter(prefix="/api/discovery", tags=["Discovery Engine (Radar)"])

class DiscoverStreamRequest(BaseModel):
    text: str
    channel_or_source: str = "Social Media Stream"
    speaker_hint: Optional[str] = None
    domain: str = "crypto"

from app.discovery.real_world_discovery import RealWorldAnalystDiscoveryService

class SearchPersonRequest(BaseModel):
    query: str
    auto_record: bool = False

@router.post("/radar/search-person")
async def search_real_world_person(payload: SearchPersonRequest, db: Session = Depends(get_db)):
    """
    Searches live global web/media for a real-life analyst or topic,
    extracts quotes, statements, forecasts, and registers candidate.
    """
    result = await RealWorldAnalystDiscoveryService.search_real_world(
        query=payload.query,
        db=db,
        limit=15,
        auto_record=payload.auto_record
    )
    return result

@router.post("/radar/live-scan")
async def live_media_scan(db: Session = Depends(get_db)):
    """
    Autonomously scans fresh live streams (Cointelegraph, Google News crypto & macro)
    for new analysts and statements.
    """
    result = await RealWorldAnalystDiscoveryService.scan_live_media(
        db=db,
        max_articles=25,
        auto_record=False
    )
    return result

@router.get("/candidates")
def get_candidates(db: Session = Depends(get_db)):
    candidates = db.query(DiscoveredSpeakerCandidate).order_by(
        DiscoveredSpeakerCandidate.mention_count.desc()
    ).all()

    unique_candidates = []
    seen_names = set()
    seen_urls = set()

    for c in candidates:
        # Strict validation: exclude random words like 'Год'
        if not is_valid_analyst_name(c.name):
            continue

        name_key = c.name.strip().lower()
        norm_url = normalize_analyst_url(c.source_url)

        # Deduplication check: if links repeat or names repeat, this is the exact same analyst
        if name_key in seen_names:
            continue
        if norm_url and norm_url in seen_urls:
            continue

        seen_names.add(name_key)
        if norm_url:
            seen_urls.add(norm_url)

        unique_candidates.append(c)

    return unique_candidates

@router.post("/candidates/{candidate_id}/approve")
def approve_candidate(candidate_id: str, db: Session = Depends(get_db)):
    res = RealWorldAnalystDiscoveryService.approve_and_record_claims(db, candidate_id)
    if not res.get("success"):
        speaker = SpeakerDiscoveryEngine.promote_candidate_to_speaker(db, candidate_id)
        if not speaker:
            raise HTTPException(status_code=404, detail="Candidate not found")
        return {"success": True, "speaker_id": speaker.id, "name": speaker.name, "statements_recorded": 0}
    return res

@router.post("/candidates/{candidate_id}/reject")
def reject_candidate(candidate_id: str, db: Session = Depends(get_db)):
    cand = db.query(DiscoveredSpeakerCandidate).filter(DiscoveredSpeakerCandidate.id == candidate_id).first()
    if not cand:
        raise HTTPException(status_code=404, detail="Candidate not found")
    cand.status = "REJECTED"
    db.commit()
    return {"success": True, "candidate_id": cand.id, "name": cand.name}

@router.post("/candidates/approve-all")
def approve_all_candidates(db: Session = Depends(get_db)):
    pending = db.query(DiscoveredSpeakerCandidate).filter(DiscoveredSpeakerCandidate.status == "CANDIDATE").all()
    count = 0
    total_stmts = 0
    for cand in pending:
        res = RealWorldAnalystDiscoveryService.approve_and_record_claims(db, cand.id)
        if res.get("success"):
            count += 1
            total_stmts += res.get("statements_recorded", 0)
    return {"success": True, "approved_count": count, "statements_recorded": total_stmts}

class CreateNarrativeRequest(BaseModel):
    topic_summary: str
    domain: str = "crypto"
    keywords: Optional[List[str]] = None

@router.get("/narratives")
def get_narratives(db: Session = Depends(get_db)):
    clusters = db.query(NarrativeCluster).order_by(
        NarrativeCluster.statement_count.desc()
    ).all()
    return clusters

@router.post("/narratives")
def create_narrative(payload: CreateNarrativeRequest, db: Session = Depends(get_db)):
    from app.engine.auto_analysis import AutoEventAnalysisEngine
    from app.oracles.auto_oracle import AutoOracleService
    from app.models.entities import Event

    domain = payload.domain.lower() if payload.domain else AutoEventAnalysisEngine.infer_domain(payload.topic_summary)

    # 1. Create narrative cluster
    cluster = NarrativeCluster(
        topic_summary=payload.topic_summary.strip(),
        domain=domain,
        key_phrases={"tokens": payload.keywords or [], "speakers": []},
        statement_count=1,
        unique_speakers_count=1,
        status="EMERGING"
    )
    db.add(cluster)
    db.commit()
    db.refresh(cluster)

    # 2. Automated system check & forecast:
    # Check if a tracked event exists, if not create one and run automated analysis & Bayesian forecasting
    existing_event = db.query(Event).filter(Event.title.ilike(payload.topic_summary.strip())).first()
    if not existing_event:
        ev = Event(
            title=payload.topic_summary.strip(),
            description=f"Тема проверена автоматической системой анализа. Ключевые слова: {', '.join(payload.keywords or [])}",
            domain=domain,
            base_rate=0.5,
            current_probability=0.5,
            status="ACTIVE"
        )
        db.add(ev)
        db.commit()
        db.refresh(ev)
        ev = AutoEventAnalysisEngine.analyze_and_forecast_event(db=db, event=ev)
    else:
        ev = existing_event

    # 3. Check live oracle verification (spot prices / deadlines)
    AutoOracleService.check_all_active_events(db=db, auto_resolve=False)

    # 4. Synchronize cluster counts with actual statements discovered
    stmt_count = len(ev.statements)
    unique_speakers = len(set(s.speaker_id for s in ev.statements))
    cluster.statement_count = max(1, stmt_count)
    cluster.unique_speakers_count = max(1, unique_speakers)
    cluster.status = "MATURE" if cluster.statement_count >= 2 else "EMERGING"
    db.commit()
    db.refresh(cluster)

    return cluster

@router.delete("/narratives/{cluster_id}")
def delete_narrative(cluster_id: str, db: Session = Depends(get_db)):
    cluster = db.query(NarrativeCluster).filter(NarrativeCluster.id == cluster_id).first()
    if not cluster:
        raise HTTPException(status_code=404, detail="Cluster not found")
    db.delete(cluster)
    db.commit()
    return {"success": True, "message": f"Тема «{cluster.topic_summary}» успешно удалена"}

@router.post("/narratives/{cluster_id}/promote")
def promote_narrative(cluster_id: str, db: Session = Depends(get_db)):
    event = EventDiscoveryEngine.promote_narrative_to_event(db, cluster_id)
    if not event:
        raise HTTPException(status_code=404, detail="Cluster not found")
    return {"success": True, "event_id": event.id, "title": event.title}

@router.post("/scan-stream")
def scan_stream(payload: DiscoverStreamRequest, db: Session = Depends(get_db)):
    """
    Ingests raw social posts or video transcript text to:
    1. Extract new potential expert names.
    2. Cluster into emerging narratives.
    """
    # 1. Speaker discovery
    extracted_names = SpeakerDiscoveryEngine.extract_potential_speakers(payload.text)
    discovered_candidates = []
    for name in extracted_names:
        cand = SpeakerDiscoveryEngine.register_or_update_candidate(
            db=db,
            name=name,
            channel_title=payload.channel_or_source,
            context_quote=payload.text[:200],
            contains_claim=True
        )
        if cand:
            discovered_candidates.append(cand.name)

    # 2. Event narrative clustering
    speaker = payload.speaker_hint or (extracted_names[0] if extracted_names else "Discovered Speaker")
    cluster = EventDiscoveryEngine.ingest_statement_to_narratives(
        db=db,
        statement_text=payload.text,
        speaker_name=speaker,
        domain=payload.domain
    )

    return {
        "success": True,
        "discovered_speakers": discovered_candidates,
        "narrative_cluster_id": cluster.id,
        "cluster_status": cluster.status,
        "cluster_topic": cluster.topic_summary,
        "unique_speakers_debating": cluster.unique_speakers_count
    }

@router.post("/seed-radar-demo")
def seed_radar_demo(db: Session = Depends(get_db)):
    """
    Seeds sample emerging narratives and discovered candidate forecasters
    to demonstrate the autonomous discovery radar in action.
    """
    # 1. Candidate Speakers
    candidates_data = [
        ("Mert Mumtaz", "Bankless & Empire Podcast", "CEO Helius, эксперт архитектуры Solana и L1", 2, 0.75),
        ("Lyn Alden", "Macro Voices", "Макроаналитик, основатель Lyn Alden Investment Strategy", 3, 0.85),
        ("Willy Woo", "Coin Bureau Interview", "On-chain аналитик, создатель метрик NVT и тепловых карт", 2, 0.80),
        ("Dan Tapiero", "Real Vision", "Основатель 10T Holdings, институциональный инвестор в Web3", 1, 0.65)
    ]
    for name, channel, quote, mentions, score in candidates_data:
        existing = db.query(DiscoveredSpeakerCandidate).filter(DiscoveredSpeakerCandidate.name == name).first()
        if not existing:
            c = DiscoveredSpeakerCandidate(
                name=name,
                discovered_via_channel=channel,
                context_quote=quote,
                mention_count=mentions,
                claim_density_score=score,
                status="CANDIDATE"
            )
            db.add(c)

    # 2. Emerging Narrative Clusters
    # Narrative 1: Solana TVL / Flippening debate (3 speakers -> Mature)
    EventDiscoveryEngine.ingest_statement_to_narratives(
        db=db,
        statement_text="Solana обойдет Ethereum по объему суточных DEX-транзакций в этом цикле",
        speaker_name="Mert Mumtaz",
        domain="crypto"
    )
    EventDiscoveryEngine.ingest_statement_to_narratives(
        db=db,
        statement_text="Solana превзойдет Ethereum по суточному объему торгов на децентрализованных биржах",
        speaker_name="Raoul Pal",
        domain="crypto"
    )
    EventDiscoveryEngine.ingest_statement_to_narratives(
        db=db,
        statement_text="DEX объем на Solana устойчиво превысит Ethereum до конца 2026",
        speaker_name="Altcoin Daily (Aaron & Austin)",
        domain="crypto"
    )

    # Narrative 2: US Strategic Bitcoin Reserve debate (2 speakers -> Emerging)
    EventDiscoveryEngine.ingest_statement_to_narratives(
        db=db,
        statement_text="США создадут Национальный стратегический резерв Биткоина (Strategic Bitcoin Reserve) до 2027",
        speaker_name="Michael Saylor",
        domain="crypto"
    )
    EventDiscoveryEngine.ingest_statement_to_narratives(
        db=db,
        statement_text="Стратегический резерв Биткоина будет принят на уровне закона в Конгрессе США",
        speaker_name="Cathie Wood",
        domain="crypto"
    )

    db.commit()
    return {"success": True, "message": "Radar demo successfully seeded with candidates and emerging narratives."}
