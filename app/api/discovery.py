from typing import List, Dict, Any, Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session
from app.database.session import get_db
from app.models.entities import DiscoveredSpeakerCandidate, NarrativeCluster, Speaker, Event
from app.discovery.speaker_discovery import SpeakerDiscoveryEngine, is_valid_analyst_name, normalize_analyst_url
from app.discovery.event_discovery import EventDiscoveryEngine
from app.discovery.real_world_discovery import RealWorldAnalystDiscoveryService
from app.discovery.social_discovery import SocialDiscoveryService
from app.engine.auto_analysis import AutoEventAnalysisEngine

router = APIRouter(prefix="/api/discovery", tags=["Discovery Engine (Radar)"])

class DiscoverStreamRequest(BaseModel):
    text: str
    channel_or_source: str = "Social Media Stream"
    speaker_hint: Optional[str] = None
    domain: str = "crypto"

class SearchPersonRequest(BaseModel):
    query: str
    auto_record: bool = False

class ManualCandidateRequest(BaseModel):
    name: str
    handle_or_channel: Optional[str] = None
    handle_or_url: Optional[str] = None
    bio: Optional[str] = None
    domain: str = "crypto"
    context_quote: Optional[str] = None
    initial_prediction: Optional[str] = None
    auto_approve: bool = False
    approve_immediately: bool = False
    search_web: bool = True

class LoadMoreCandidatesRequest(BaseModel):
    offset: int = 0
    limit: int = 6
    query: Optional[str] = None

def _serialize_candidate(c: DiscoveredSpeakerCandidate) -> Dict[str, Any]:
    curated = SocialDiscoveryService.get_curated_entry(c.name)
    socials = SocialDiscoveryService.discover_socials_for_person(
        name=c.name,
        handle_or_channel=c.discovered_via_channel,
        context_text=c.context_quote
    )
    preds = c.extracted_predictions or []
    if not preds and curated and curated.get("predictions"):
        preds = curated["predictions"]
    return {
        "id": c.id,
        "name": c.name,
        "discovered_via_channel": c.discovered_via_channel,
        "bio": curated["bio"] if curated else f"Обнаружен в источнике: {c.discovered_via_channel}",
        "domain": curated["domain"] if curated else AutoEventAnalysisEngine.infer_domain(c.context_quote or c.name),
        "context_quote": c.context_quote or (curated["quote"] if curated else ""),
        "source_url": c.source_url,
        "extracted_predictions": preds,
        "mention_count": c.mention_count,
        "claim_density_score": c.claim_density_score,
        "status": c.status,
        "created_at": c.created_at,
        "social_accounts": socials
    }

def _serialize_narrative(cluster: NarrativeCluster, db: Session) -> Dict[str, Any]:
    tokens = (cluster.key_phrases or {}).get("tokens", [])
    linked_event = db.query(Event).filter(Event.title.ilike(cluster.topic_summary.strip())).first()
    prob = linked_event.current_probability if linked_event else 0.55

    ai_analysis = AutoEventAnalysisEngine.generate_ai_topic_analysis(
        title=cluster.topic_summary,
        domain=cluster.domain,
        probability=prob,
        statements_count=cluster.statement_count,
        keywords=tokens
    )
    return {
        "id": cluster.id,
        "topic_summary": cluster.topic_summary,
        "domain": cluster.domain,
        "key_phrases": cluster.key_phrases or {"tokens": [], "speakers": []},
        "statement_count": cluster.statement_count,
        "unique_speakers_count": cluster.unique_speakers_count,
        "status": cluster.status,
        "promoted_event_id": cluster.promoted_event_id or (linked_event.id if linked_event else None),
        "created_at": cluster.created_at,
        "ai_analysis": ai_analysis
    }

@router.get("/social-lookup")
def lookup_candidate_socials(
    name: str = Query(..., description="Analyst or candidate name"),
    handle: Optional[str] = Query(None, description="Optional handle or channel")
):
    curated = SocialDiscoveryService.get_curated_entry(name)
    socials = SocialDiscoveryService.discover_socials_for_person(name=name, handle_or_channel=handle)
    return {
        "name": name.strip(),
        "bio": curated["bio"] if curated else "Независимый аналитик и эксперт рынка",
        "domain": curated["domain"] if curated else "crypto",
        "quote": curated["quote"] if curated else "",
        "social_accounts": socials
    }

@router.post("/radar/search-person")
async def search_real_world_person(payload: SearchPersonRequest, db: Session = Depends(get_db)):
    """
    Searches live global web/media for a real-life analyst or topic,
    extracts quotes, statements, forecasts, and registers candidate.
    Also checks curated directory for instant match & social links.
    """
    q_clean = payload.query.strip()
    curated = SocialDiscoveryService.get_curated_entry(q_clean)
    if curated:
        existing = db.query(DiscoveredSpeakerCandidate).filter(
            DiscoveredSpeakerCandidate.name.ilike(curated["name"])
        ).first()
        if not existing:
            cand = DiscoveredSpeakerCandidate(
                name=curated["name"],
                discovered_via_channel=curated["channel"],
                context_quote=curated["quote"],
                mention_count=2,
                claim_density_score=0.82,
                status="CANDIDATE",
                extracted_predictions=curated.get("predictions", [])
            )
            db.add(cand)
            db.commit()

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

@router.post("/radar/load-more")
async def load_more_radar_candidates(payload: LoadMoreCandidatesRequest, db: Session = Depends(get_db)):
    """
    Progressive discovery endpoint for infinite scroll in Candidate Radar.
    Discovers additional analysts from curated directory and live media streams.
    """
    existing_names = {
        c.name.strip().lower()
        for c in db.query(DiscoveredSpeakerCandidate).all()
    }
    speaker_names = {
        s.name.strip().lower()
        for s in db.query(Speaker).all()
    }

    added_candidates = []
    q_filter = (payload.query or "").strip().lower()

    # 1. Pull next batch from curated global & RU analysts directory
    for item in SocialDiscoveryService.CURATED_ANALYSTS:
        c_name_low = item["name"].strip().lower()
        if c_name_low in existing_names:
            continue
        if q_filter and q_filter not in c_name_low and q_filter not in item.get("bio", "").lower() and q_filter not in item.get("domain", "").lower():
            continue

        status_val = "APPROVED" if c_name_low in speaker_names else "CANDIDATE"
        cand = DiscoveredSpeakerCandidate(
            name=item["name"],
            discovered_via_channel=item["channel"],
            context_quote=item["quote"],
            mention_count=2,
            claim_density_score=0.80,
            status=status_val,
            extracted_predictions=item.get("predictions", [])
        )
        db.add(cand)
        db.commit()
        db.refresh(cand)
        existing_names.add(c_name_low)
        added_candidates.append(_serialize_candidate(cand))

        if len(added_candidates) >= payload.limit:
            break

    # 2. If user provided a specific search query or curated pool is exhausted, scan live media
    if len(added_candidates) == 0 and q_filter:
        await RealWorldAnalystDiscoveryService.search_real_world(
            query=payload.query.strip(),
            db=db,
            limit=10,
            auto_record=False
        )

    total_remaining = sum(
        1 for item in SocialDiscoveryService.CURATED_ANALYSTS
        if item["name"].strip().lower() not in existing_names
    )
    all_cands = db.query(DiscoveredSpeakerCandidate).order_by(DiscoveredSpeakerCandidate.mention_count.desc()).all()
    items_slice = [_serialize_candidate(c) for c in all_cands[payload.offset: payload.offset + payload.limit]] or added_candidates

    return {
        "success": True,
        "added_count": len(added_candidates),
        "new_candidates": added_candidates,
        "items": items_slice,
        "total_count": len(all_cands),
        "has_more": total_remaining > 0
    }

@router.post("/candidates/manual")
async def create_manual_candidate(payload: ManualCandidateRequest, db: Session = Depends(get_db)):
    """
    Manually adds a candidate analyst, automatically discovers all their social networks
    (X, YouTube, Telegram, Web) and pulls their forecasts from media.
    """
    raw_name = payload.name.strip()
    if not raw_name or len(raw_name) < 2:
        raise HTTPException(status_code=400, detail="Введите корректное имя кандидата")

    handle_val = payload.handle_or_channel or payload.handle_or_url
    quote_val = payload.context_quote or payload.initial_prediction
    should_approve = payload.auto_approve or payload.approve_immediately

    # Format name cleanly
    formatted_name = " ".join(w.capitalize() for w in raw_name.split())
    curated = SocialDiscoveryService.get_curated_entry(formatted_name)
    if curated:
        formatted_name = curated["name"]

    if not is_valid_analyst_name(formatted_name) and not curated:
        raise HTTPException(
            status_code=400,
            detail="Имя должно состоять из реальных имени и фамилии (без случайных слов и цифр)"
        )

    existing = db.query(DiscoveredSpeakerCandidate).filter(
        DiscoveredSpeakerCandidate.name.ilike(formatted_name)
    ).first()

    socials = SocialDiscoveryService.discover_socials_for_person(
        name=formatted_name,
        handle_or_channel=handle_val,
        context_text=quote_val
    )

    channel_label = handle_val or (curated["channel"] if curated else "Добавлен вручную + Автопоиск сетей")
    quote_text = quote_val or (curated["quote"] if curated else f"Эксперт в сфере {payload.domain}. Профиль и соцсети подтянуты автоматически.")
    preds = curated.get("predictions", []) if curated else []

    if not preds and quote_val:
        preds = [{
            "event_hypothesis": quote_val[:160],
            "domain": payload.domain or AutoEventAnalysisEngine.infer_domain(quote_val),
            "speaker_confidence": 0.78,
            "raw_quote": quote_val
        }]

    if existing:
        existing.mention_count += 1
        if handle_val:
            existing.discovered_via_channel = handle_val
        if quote_val:
            existing.context_quote = quote_val
        if preds and not existing.extracted_predictions:
            existing.extracted_predictions = preds
        cand = existing
    else:
        cand = DiscoveredSpeakerCandidate(
            name=formatted_name,
            discovered_via_channel=channel_label,
            context_quote=quote_text,
            mention_count=2,
            claim_density_score=0.80,
            status="CANDIDATE",
            extracted_predictions=preds
        )
        db.add(cand)

    db.commit()
    db.refresh(cand)

    # Optionally search live web for additional statements
    if payload.search_web and not preds:
        try:
            await RealWorldAnalystDiscoveryService.search_real_world(
                query=formatted_name,
                db=db,
                limit=8,
                auto_record=False
            )
            db.refresh(cand)
        except Exception:
            pass

    if should_approve:
        RealWorldAnalystDiscoveryService.approve_and_record_claims(db, cand.id)
        db.refresh(cand)

    return {
        "success": True,
        "name": cand.name,
        "candidate": _serialize_candidate(cand),
        "social_accounts": socials
    }

@router.post("/candidates/{candidate_id}/fetch-socials")
async def fetch_candidate_socials_and_claims(candidate_id: str, db: Session = Depends(get_db)):
    """
    Actively discovers/refreshes all social networks and searches live media
    for additional statements for a specific candidate.
    """
    cand = db.query(DiscoveredSpeakerCandidate).filter(DiscoveredSpeakerCandidate.id == candidate_id).first()
    if not cand:
        raise HTTPException(status_code=404, detail="Кандидат не найден")

    curated = SocialDiscoveryService.get_curated_entry(cand.name)
    if curated:
        if not cand.extracted_predictions and curated.get("predictions"):
            cand.extracted_predictions = curated["predictions"]
        if (not cand.context_quote or len(cand.context_quote) < 35) and curated.get("quote"):
            cand.context_quote = curated["quote"]
        db.commit()

    try:
        await RealWorldAnalystDiscoveryService.search_real_world(
            query=cand.name,
            db=db,
            limit=8,
            auto_record=False
        )
        db.refresh(cand)
    except Exception:
        pass

    serialized = _serialize_candidate(cand)
    return {
        "success": True,
        "name": cand.name,
        "candidate": serialized,
        "social_accounts": serialized["social_accounts"]
    }

@router.get("/candidates")
def get_candidates(db: Session = Depends(get_db)):
    candidates = db.query(DiscoveredSpeakerCandidate).order_by(
        DiscoveredSpeakerCandidate.mention_count.desc()
    ).all()

    # Ensure initial rich pool of candidates if DB has very few
    valid_existing = [c for c in candidates if is_valid_analyst_name(c.name)]
    if len(valid_existing) < 8:
        existing_names = {c.name.strip().lower() for c in valid_existing}
        speaker_names = {s.name.strip().lower() for s in db.query(Speaker).all()}
        for item in SocialDiscoveryService.CURATED_ANALYSTS[:10]:
            c_low = item["name"].strip().lower()
            if c_low not in existing_names:
                cand = DiscoveredSpeakerCandidate(
                    name=item["name"],
                    discovered_via_channel=item["channel"],
                    context_quote=item["quote"],
                    mention_count=2,
                    claim_density_score=0.80,
                    status="APPROVED" if c_low in speaker_names else "CANDIDATE",
                    extracted_predictions=item.get("predictions", [])
                )
                db.add(cand)
                existing_names.add(c_low)
        db.commit()
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

        unique_candidates.append(_serialize_candidate(c))

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
        if not is_valid_analyst_name(cand.name):
            continue
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
    return [_serialize_narrative(c, db) for c in clusters]

@router.get("/narratives/{cluster_id}/ai-summary")
def get_narrative_ai_summary(cluster_id: str, db: Session = Depends(get_db)):
    cluster = db.query(NarrativeCluster).filter(NarrativeCluster.id == cluster_id).first()
    if not cluster:
        raise HTTPException(status_code=404, detail="Cluster not found")
    return _serialize_narrative(cluster, db)["ai_analysis"]

@router.post("/narratives")
def create_narrative(payload: CreateNarrativeRequest, db: Session = Depends(get_db)):
    from app.oracles.auto_oracle import AutoOracleService

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
    existing_event = db.query(Event).filter(Event.title.ilike(payload.topic_summary.strip())).first()
    if not existing_event:
        ai_init = AutoEventAnalysisEngine.generate_ai_topic_analysis(
            title=payload.topic_summary.strip(),
            domain=domain,
            keywords=payload.keywords or []
        )
        ev = Event(
            title=payload.topic_summary.strip(),
            description=ai_init["summary"],
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

    return _serialize_narrative(cluster, db)

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
