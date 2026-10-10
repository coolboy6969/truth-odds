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

class LoadMoreNarrativesRequest(BaseModel):
    offset: int = 0
    limit: int = 6
    query: Optional[str] = None
    domain: Optional[str] = None

class SearchNarrativesRequest(BaseModel):
    query: str
    domain: Optional[str] = None

CURATED_EVALUATION_TOPICS: List[Dict[str, Any]] = [
    {
        "topic_summary": "Solana превзойдет Ethereum по суточному объему торгов на DEX до конца 2026 года",
        "domain": "crypto",
        "tokens": ["solana", "ethereum", "dex", "tvl", "flippening", "солана", "эфириум"],
        "speakers": ["Raoul Pal", "Mert Mumtaz", "Altcoin Daily (Aaron & Austin)"],
        "statement_count": 5,
        "unique_speakers_count": 3,
        "status": "MATURE"
    },
    {
        "topic_summary": "США создадут Национальный стратегический резерв Биткоина на уровне федерального закона",
        "domain": "crypto",
        "tokens": ["bitcoin", "reserve", "usa", "treasury", "etf", "биткоин", "резерв", "сша"],
        "speakers": ["Michael Saylor", "Cathie Wood", "Arthur Hayes"],
        "statement_count": 6,
        "unique_speakers_count": 3,
        "status": "MATURE"
    },
    {
        "topic_summary": "ФРС США снизит ключевую процентную ставку ниже 3.5% в течение ближайших 12 месяцев",
        "domain": "macro",
        "tokens": ["fed", "rates", "cpi", "inflation", "liquidity", "фрс", "ставка", "инфляция"],
        "speakers": ["Lyn Alden", "Arthur Hayes", "Raoul Pal"],
        "statement_count": 5,
        "unique_speakers_count": 3,
        "status": "MATURE"
    },
    {
        "topic_summary": "ИИ-агенты будут автономно выполнять более 40% задач разработки ПО в тех-компаниях к 2027 году",
        "domain": "tech",
        "tokens": ["ai", "agents", "software", "coding", "automation", "ии", "агенты", "разработка"],
        "speakers": ["Cathie Wood", "Sam Altman", "Elon Musk"],
        "statement_count": 4,
        "unique_speakers_count": 3,
        "status": "MATURE"
    },
    {
        "topic_summary": "Совокупная капитализация рынка стейблкоинов (USDT, USDC) превысит $300 млрд до конца 2026 года",
        "domain": "crypto",
        "tokens": ["stablecoins", "usdt", "usdc", "liquidity", "payments", "стейблкоины", "ликвидность"],
        "speakers": ["Willy Woo", "Lyn Alden", "Dan Tapiero"],
        "statement_count": 4,
        "unique_speakers_count": 3,
        "status": "MATURE"
    },
    {
        "topic_summary": "Цена золота превысит $3,200 за унцию на фоне рекордных закупок мировыми центробанками",
        "domain": "macro",
        "tokens": ["gold", "central-banks", "inflation", "commodities", "macro", "золото", "центробанки"],
        "speakers": ["Peter Schiff", "Lyn Alden", "Евгений Коган"],
        "statement_count": 5,
        "unique_speakers_count": 3,
        "status": "MATURE"
    },
    {
        "topic_summary": "Регулятор SEC в США одобрит спотовые ETF на Solana и XRP для институциональных инвесторов",
        "domain": "crypto",
        "tokens": ["sec", "etf", "solana", "xrp", "institutional", "спотовый", "институционалы"],
        "speakers": ["Guy Turner (Coin Bureau)", "Cathie Wood", "Raoul Pal"],
        "statement_count": 4,
        "unique_speakers_count": 3,
        "status": "MATURE"
    },
    {
        "topic_summary": "Индекс S&P 500 обновит исторический максимум выше 6,500 пунктов благодаря прибыли сектора ИИ",
        "domain": "macro",
        "tokens": ["sp500", "equities", "ai-stocks", "earnings", "wall-street", "акции", "фондовый"],
        "speakers": ["Tom Lee", "Cathie Wood", "Евгений Коган"],
        "statement_count": 4,
        "unique_speakers_count": 3,
        "status": "MATURE"
    },
    {
        "topic_summary": "Объем токенизированных реальных активов (RWA) на блокчейне превысит $50 млрд",
        "domain": "crypto",
        "tokens": ["rwa", "tokenization", "blackrock", "ethereum", "defi", "токенизация"],
        "speakers": ["Larry Fink", "Raoul Pal", "Vitalik Buterin"],
        "statement_count": 4,
        "unique_speakers_count": 3,
        "status": "MATURE"
    },
    {
        "topic_summary": "Ведущие AI-лаборатории представят модель с автономным научным рассуждением уровня AGI до 2027 года",
        "domain": "tech",
        "tokens": ["agi", "llm", "reasoning", "openai", "compute", "нейросети", "интеллект"],
        "speakers": ["Sam Altman", "Elon Musk", "Cathie Wood"],
        "statement_count": 4,
        "unique_speakers_count": 3,
        "status": "MATURE"
    },
    {
        "topic_summary": "Доля Биткоина в казначейских резервах компаний из индекса Nasdaq-100 превысит 5%",
        "domain": "crypto",
        "tokens": ["bitcoin", "nasdaq", "corporate-treasury", "microstrategy", "биткоин", "корпорации"],
        "speakers": ["Michael Saylor", "PlanB", "Dan Tapiero"],
        "statement_count": 4,
        "unique_speakers_count": 3,
        "status": "MATURE"
    },
    {
        "topic_summary": "Сеть второго уровня Base (Coinbase) станет лидером среди всех L2 Ethereum по числу активных адресов",
        "domain": "crypto",
        "tokens": ["base", "layer2", "ethereum", "coinbase", "scaling", "l2", "эфир"],
        "speakers": ["Vitalik Buterin", "Guy Turner (Coin Bureau)"],
        "statement_count": 3,
        "unique_speakers_count": 2,
        "status": "MATURE"
    },
    {
        "topic_summary": "Выручка производителей чипов для ИИ и дата-центров вырастет более чем на 50% за годовой цикл",
        "domain": "tech",
        "tokens": ["semiconductors", "gpu", "datacenter", "ai-hardware", "nvidia", "чипы", "видеокарты"],
        "speakers": ["Cathie Wood", "Raoul Pal"],
        "statement_count": 3,
        "unique_speakers_count": 2,
        "status": "MATURE"
    },
    {
        "topic_summary": "Инфляция CPI в США стабилизируется у целевого уровня 2.0% без наступления рецессии",
        "domain": "macro",
        "tokens": ["cpi", "soft-landing", "macro", "us-economy", "инфляция", "рецессия", "экономика"],
        "speakers": ["Tom Lee", "Lyn Alden"],
        "statement_count": 3,
        "unique_speakers_count": 2,
        "status": "MATURE"
    },
    {
        "topic_summary": "Автономные роботы-гуманоиды начнут серийно применяться на промышленных предприятиях до 2027 года",
        "domain": "tech",
        "tokens": ["robotics", "humanoid", "optimus", "manufacturing", "ai", "роботы", "автоматизация"],
        "speakers": ["Elon Musk", "Cathie Wood"],
        "statement_count": 3,
        "unique_speakers_count": 2,
        "status": "MATURE"
    },
    {
        "topic_summary": "Государственный долг США превысит $38 трлн, ускорив переток капитала в твердые активы (BTC и золото)",
        "domain": "macro",
        "tokens": ["us-debt", "fiscal-deficit", "bitcoin", "gold", "debasement", "госдолг", "дефицит"],
        "speakers": ["Arthur Hayes", "Lyn Alden", "Robert Kiyosaki"],
        "statement_count": 4,
        "unique_speakers_count": 3,
        "status": "MATURE"
    },
    {
        "topic_summary": "Биткоин преодолеет отметку $150,000 на фоне расширения глобальной долларовой ликвидности M2",
        "domain": "crypto",
        "tokens": ["bitcoin", "btc", "150k", "m2", "liquidity", "биткоин", "рост"],
        "speakers": ["Arthur Hayes", "Michael Saylor", "PlanB"],
        "statement_count": 6,
        "unique_speakers_count": 3,
        "status": "MATURE"
    },
    {
        "topic_summary": "Ethereum обновит исторический максимум выше $5,000 за счет институционального стейкинга и ETF",
        "domain": "crypto",
        "tokens": ["ethereum", "eth", "staking", "etf", "5000", "эфириум", "стейкинг"],
        "speakers": ["Vitalik Buterin", "Raoul Pal", "Кирилл Эванс"],
        "statement_count": 4,
        "unique_speakers_count": 3,
        "status": "MATURE"
    },
    {
        "topic_summary": "Доминация Биткоина (BTC.D) начнет фазу снижения ниже 52%, запустив широкий сезон альткоинов",
        "domain": "crypto",
        "tokens": ["btcd", "altseason", "dominance", "altcoins", "альтсезон", "доминация", "альткоины"],
        "speakers": ["Benjamin Cowen", "Рафаэль Манвелян", "Guy Turner (Coin Bureau)"],
        "statement_count": 4,
        "unique_speakers_count": 3,
        "status": "MATURE"
    },
    {
        "topic_summary": "Крупнейшие тех-гиганты (Big Tech) подпишут контракты на строительство малых модульных АЭС для ИИ-ЦОД",
        "domain": "tech",
        "tokens": ["nuclear", "energy", "datacenter", "ai", "big-tech", "энергетика", "аэс"],
        "speakers": ["Sam Altman", "Lyn Alden", "Cathie Wood"],
        "statement_count": 3,
        "unique_speakers_count": 3,
        "status": "MATURE"
    },
    {
        "topic_summary": "Индекс доллара США (DXY) опустится ниже отметки 98 на фоне цикла снижения ставок ФРС",
        "domain": "macro",
        "tokens": ["dxy", "dollar", "forex", "fed", "macro", "доллар", "валюта"],
        "speakers": ["Arthur Hayes", "Raoul Pal", "Lyn Alden"],
        "statement_count": 3,
        "unique_speakers_count": 3,
        "status": "MATURE"
    },
    {
        "topic_summary": "Общая заблокированная стоимость (TVL) в протоколах DeFi превысит $250 млрд",
        "domain": "crypto",
        "tokens": ["defi", "tvl", "yield", "lending", "dex", "дефи", "ликвидность"],
        "speakers": ["Vitalik Buterin", "Анатолий Радченко", "Mert Mumtaz"],
        "statement_count": 3,
        "unique_speakers_count": 3,
        "status": "MATURE"
    },
    {
        "topic_summary": "Сеть TON и экосистема мини-приложений привлекут более 100 млн активных крипто-кошельков",
        "domain": "crypto",
        "tokens": ["ton", "web3", "wallets", "adoption", "кошельки", "массовое-принятие"],
        "speakers": ["Рафаэль Манвелян", "Кирилл Эванс", "Анатолий Радченко"],
        "statement_count": 3,
        "unique_speakers_count": 3,
        "status": "EMERGING"
    },
    {
        "topic_summary": "Открытые (open-weight) языковые модели сравняются по качеству рассуждений с проприетарными флагманами",
        "domain": "tech",
        "tokens": ["open-source", "llm", "ai", "benchmarks", "модели", "ии"],
        "speakers": ["Balaji Srinivasan", "Sam Altman", "Cathie Wood"],
        "statement_count": 3,
        "unique_speakers_count": 3,
        "status": "MATURE"
    },
    {
        "topic_summary": "Беспилотные роботакси получат разрешение на коммерческую эксплуатацию без водителя в 10+ мегаполисах",
        "domain": "tech",
        "tokens": ["robotaxi", "autonomous", "tesla", "waymo", "ai", "беспилотники", "роботакси"],
        "speakers": ["Cathie Wood", "Elon Musk"],
        "statement_count": 3,
        "unique_speakers_count": 2,
        "status": "MATURE"
    },
    {
        "topic_summary": "Доходность 10-летних казначейских облигаций США (US10Y) снизится ниже 3.75%",
        "domain": "macro",
        "tokens": ["bonds", "treasuries", "us10y", "yield", "облигации", "трежерис", "макро"],
        "speakers": ["Lyn Alden", "Евгений Коган", "Tom Lee"],
        "statement_count": 3,
        "unique_speakers_count": 3,
        "status": "MATURE"
    },
    {
        "topic_summary": "Суверенные фонды благосостояния стран Ближнего Востока и Азии раскроют владение спотовым Bitcoin",
        "domain": "crypto",
        "tokens": ["sovereign-wealth", "bitcoin", "institutions", "adoption", "фонды", "институционалы"],
        "speakers": ["Michael Saylor", "Dan Tapiero", "Anthony Pompliano"],
        "statement_count": 4,
        "unique_speakers_count": 3,
        "status": "MATURE"
    },
    {
        "topic_summary": "Децентрализованные сети физических вычислений (DePIN) покажут трехкратный рост выручки за год",
        "domain": "crypto",
        "tokens": ["depin", "compute", "solana", "ai-crypto", "инфраструктура"],
        "speakers": ["Mert Mumtaz", "Raoul Pal", "Анатолий Радченко"],
        "statement_count": 3,
        "unique_speakers_count": 3,
        "status": "EMERGING"
    },
    {
        "topic_summary": "Банк Японии продолжит нормализацию ставок, вызывая репатриацию капитала и волатильность кэрри-трейда",
        "domain": "macro",
        "tokens": ["boj", "japan", "yen", "carry-trade", "macro", "япония", "иена"],
        "speakers": ["Arthur Hayes", "Lyn Alden"],
        "statement_count": 3,
        "unique_speakers_count": 2,
        "status": "MATURE"
    },
    {
        "topic_summary": "Стоимость инференса (запроса к LLM) снизится еще на 80% благодаря специализированным AI-чипам (ASIC)",
        "domain": "tech",
        "tokens": ["inference", "asic", "tpu", "llm", "cost", "чипы", "инференс"],
        "speakers": ["Sam Altman", "Cathie Wood", "Balaji Srinivasan"],
        "statement_count": 3,
        "unique_speakers_count": 3,
        "status": "MATURE"
    },
    {
        "topic_summary": "Серебро преодолеет отметку $40 за унцию на фоне дефицита промышленного предложения для солнечной энергетики",
        "domain": "macro",
        "tokens": ["silver", "commodities", "solar", "inflation", "серебро", "сырье", "металлы"],
        "speakers": ["Peter Schiff", "Robert Kiyosaki", "Евгений Коган"],
        "statement_count": 3,
        "unique_speakers_count": 3,
        "status": "EMERGING"
    },
    {
        "topic_summary": "Нео-банки и платежные гиганты (Visa, Mastercard, Stripe) переведут более 15% трансграничных расчетов на стейблкоины",
        "domain": "crypto",
        "tokens": ["payments", "visa", "stripe", "stablecoins", "fintech", "платежи", "финтех"],
        "speakers": ["Willy Woo", "Anthony Pompliano", "Dan Tapiero"],
        "statement_count": 3,
        "unique_speakers_count": 3,
        "status": "MATURE"
    },
    {
        "topic_summary": "Капитализация сектора технологических компаний Nasdaq-100 вырастет более чем на 20% за календарный год",
        "domain": "tech",
        "tokens": ["nasdaq", "tech-stocks", "growth", "ai", "технологии", "акции"],
        "speakers": ["Tom Lee", "Cathie Wood", "Василий Олейник"],
        "statement_count": 3,
        "unique_speakers_count": 3,
        "status": "MATURE"
    },
    {
        "topic_summary": "Объем резервов Bitcoin на централизованных биржах (CEX) упадет до нового 5-летнего минимума",
        "domain": "crypto",
        "tokens": ["onchain", "exchange-reserves", "supply-shock", "btc", "ончейн", "резервы", "биржи"],
        "speakers": ["Willy Woo", "PlanB", "Benjamin Cowen"],
        "statement_count": 4,
        "unique_speakers_count": 3,
        "status": "MATURE"
    },
    {
        "topic_summary": "Глобальный индекс деловой активности в промышленности (Global Manufacturing PMI) закрепится выше 51 пункта",
        "domain": "macro",
        "tokens": ["pmi", "business-cycle", "macro", "manufacturing", "цикл", "экономика"],
        "speakers": ["Raoul Pal", "Lyn Alden", "Александр Герчик"],
        "statement_count": 3,
        "unique_speakers_count": 3,
        "status": "MATURE"
    },
    {
        "topic_summary": "Клиентское обновление Firedancer в сети Solana обеспечит пропускную способность свыше 100,000 TPS в мейннете",
        "domain": "crypto",
        "tokens": ["firedancer", "solana", "tps", "scaling", "блокчейн", "солана"],
        "speakers": ["Mert Mumtaz", "Raoul Pal"],
        "statement_count": 3,
        "unique_speakers_count": 2,
        "status": "EMERGING"
    },
]


def _synthesize_feed_topics(
    query: str,
    domain: Optional[str],
    existing_titles: set,
    count: int = 6,
    batch_seed: int = 0
) -> List[Dict[str, Any]]:
    """
    Dynamically generates realistic, non-duplicate evaluation topics for the topic feed
    so that scrolling down or searching in 'Поиск тем для оценки' always yields a rich feed.
    """
    q_clean = (query or "").strip().lstrip("#")
    inferred_dom = (domain or "").strip().lower() or (
        AutoEventAnalysisEngine.infer_domain(q_clean) if q_clean else "crypto"
    )
    if inferred_dom not in ("crypto", "macro", "tech", "general"):
        inferred_dom = "crypto"

    default_speakers_map = {
        "crypto": ["Arthur Hayes", "Michael Saylor", "Raoul Pal", "Willy Woo"],
        "macro": ["Lyn Alden", "Raoul Pal", "Tom Lee", "Евгений Коган"],
        "tech": ["Cathie Wood", "Sam Altman", "Balaji Srinivasan"],
        "general": ["Raoul Pal", "Lyn Alden", "Tom Lee"],
    }

    if q_clean:
        subj = q_clean[0].upper() + q_clean[1:] if len(q_clean) > 1 else q_clean.upper()
        base_tokens = [w.lower().strip(".,?!:;()") for w in q_clean.split() if len(w.strip(".,?!:;()")) >= 2][:4]
        templates = [
            (f"{subj}: достижение верхнего целевого ориентира аналитиков до конца 2026 года", "MATURE", 4),
            (f"Институциональный приток капитала и рост спроса в направлении «{subj}» в ближайшие 12 месяцев", "MATURE", 4),
            (f"{subj}: опережающая динамика относительно рыночного бенчмарка по итогам полугодия", "MATURE", 3),
            (f"Регуляторное одобрение и расширение инфраструктуры для сегмента «{subj}»", "EMERGING", 3),
            (f"Удержание ключевых фундаментальных метрик и тренда по теме «{subj}» без глубокой просадки", "MATURE", 3),
            (f"Достижение консенсус-прогноза ведущих макро- и крипто-экспертов по сценарию «{subj}»", "MATURE", 4),
        ]
        result = []
        for idx, (tpl_title, st_val, stmt_cnt) in enumerate(templates):
            if tpl_title.strip().lower() in existing_titles:
                continue
            sp_list = default_speakers_map.get(inferred_dom, default_speakers_map["crypto"])[:3]
            result.append({
                "topic_summary": tpl_title,
                "domain": inferred_dom,
                "tokens": base_tokens + [inferred_dom, "forecast"],
                "speakers": sp_list,
                "statement_count": stmt_cnt,
                "unique_speakers_count": len(sp_list),
                "status": st_val
            })
            if len(result) >= count:
                break
        return result

    # When scrolling the feed without a specific query, generate varied market feed topics
    feed_subjects = [
        ("crypto", "Рост доли институциональных кастодианов в хранении Bitcoin и Ethereum свыше 25% эмиссии", ["custody", "institutions", "btc", "eth"]),
        ("macro", "Смягчение финансовых условий и рост глобального индекса ликвидности ЦБ на +12% за год", ["liquidity", "central-banks", "macro", "m2"]),
        ("tech", "Увеличение доли ИИ-ассистентов в корпоративных SaaS-платформах до 75% компаний Fortune 500", ["saas", "enterprise-ai", "fortune500", "automation"]),
        ("crypto", "Превышение суточного объема расчетов в сетях L2 над основной сетью Ethereum более чем в 10 раз", ["layer2", "ethereum", "scaling", "tps"]),
        ("macro", "Сохранение положительной реальной доходности на рынке казначейских облигаций при росте ВВП США", ["gdp", "yields", "macro", "treasuries"]),
        ("tech", "Выпуск коммерческих локальных ИИ-моделей на смартфонах и ноутбуках без облачной задержки", ["edge-ai", "npu", "hardware", "llm"]),
        ("crypto", "Удвоение капитализации децентрализованных деривативных протоколов (Perp DEX) за 12 месяцев", ["perp-dex", "defi", "derivatives", "trading"]),
        ("macro", "Приток капитала на развивающиеся рынки (Emerging Markets) на фоне ослабления доллара США", ["emerging-markets", "dxy", "capital-flows", "macro"]),
        ("tech", "Сокращение сроков разработки новых лекарств с помощью генеративных био-моделей ИИ на 40%", ["biotech", "ai-drug-discovery", "healthcare", "tech"]),
        ("crypto", "Внедрение стандарта абстракции аккаунтов и смарт-кошельков у 50+ млн пользователей Web3", ["account-abstraction", "wallets", "web3", "adoption"]),
        ("macro", "Рост цен на медь и стратегические металлы более чем на 25% из-за электрификации и строительства ЦОД", ["copper", "commodities", "datacenter", "macro"]),
        ("tech", "Превышение порога в $200 млрд годовых инвестиций облачных гиперскейлеров в ИИ-инфраструктуру", ["capex", "hyperscalers", "cloud", "ai"]),
    ]

    result = []
    cycle_num = max(1, (batch_seed // len(feed_subjects)) + 1)
    for dom_val, base_title, toks in feed_subjects:
        if domain and dom_val != domain.lower():
            continue
        candidate_title = base_title if cycle_num == 1 else f"{base_title} (волна оценки #{cycle_num})"
        if candidate_title.strip().lower() in existing_titles:
            continue
        sp_list = default_speakers_map.get(dom_val, default_speakers_map["crypto"])[:3]
        result.append({
            "topic_summary": candidate_title,
            "domain": dom_val,
            "tokens": toks,
            "speakers": sp_list,
            "statement_count": 3,
            "unique_speakers_count": len(sp_list),
            "status": "MATURE"
        })
        if len(result) >= count:
            break
    return result


@router.get("/narratives")
def get_narratives(db: Session = Depends(get_db)):
    clusters = db.query(NarrativeCluster).order_by(
        NarrativeCluster.statement_count.desc()
    ).all()

    # Seed a rich initial feed of evaluation topics (at least 18 topics) so the feed is full right away
    if len(clusters) < 18:
        existing_titles = {c.topic_summary.strip().lower() for c in clusters}
        for item in CURATED_EVALUATION_TOPICS[:18]:
            t_low = item["topic_summary"].strip().lower()
            if t_low not in existing_titles:
                nc = NarrativeCluster(
                    topic_summary=item["topic_summary"],
                    domain=item["domain"],
                    key_phrases={"tokens": item["tokens"], "speakers": item["speakers"]},
                    statement_count=item["statement_count"],
                    unique_speakers_count=item["unique_speakers_count"],
                    status=item["status"]
                )
                db.add(nc)
                existing_titles.add(t_low)
        db.commit()
        clusters = db.query(NarrativeCluster).order_by(
            NarrativeCluster.statement_count.desc()
        ).all()

    # Deduplicate by topic_summary
    unique_clusters = []
    seen_topics = set()
    for c in clusters:
        t_key = c.topic_summary.strip().lower()
        if t_key in seen_topics:
            continue
        seen_topics.add(t_key)
        unique_clusters.append(_serialize_narrative(c, db))

    return unique_clusters


@router.post("/narratives/load-more")
def load_more_narratives(payload: LoadMoreNarrativesRequest, db: Session = Depends(get_db)):
    """
    Progressive discovery endpoint for infinite scroll feed in 'Поиск тем для оценки'.
    Loads additional topics from the 36+ curated catalog and dynamically synthesizes new feed topics
    when the catalog is exhausted so the feed never ends.
    """
    existing_titles = {
        c.topic_summary.strip().lower()
        for c in db.query(NarrativeCluster).all()
    }
    q_filter = (payload.query or "").strip().lower().lstrip("#")
    dom_filter = (payload.domain or "").strip().lower()
    batch_limit = max(6, payload.limit or 6)

    added_clusters = []
    for item in CURATED_EVALUATION_TOPICS:
        t_low = item["topic_summary"].strip().lower()
        if t_low in existing_titles:
            continue
        if dom_filter and item["domain"].lower() != dom_filter:
            continue
        if q_filter:
            in_title = q_filter in t_low
            in_tokens = any(q_filter in tok.lower() for tok in item.get("tokens", []))
            in_speakers = any(q_filter in sp.lower() for sp in item.get("speakers", []))
            if not (in_title or in_tokens or in_speakers):
                continue

        nc = NarrativeCluster(
            topic_summary=item["topic_summary"],
            domain=item["domain"],
            key_phrases={"tokens": item["tokens"], "speakers": item["speakers"]},
            statement_count=item["statement_count"],
            unique_speakers_count=item["unique_speakers_count"],
            status=item["status"]
        )
        db.add(nc)
        db.commit()
        db.refresh(nc)
        existing_titles.add(t_low)
        added_clusters.append(_serialize_narrative(nc, db))

        if len(added_clusters) >= batch_limit:
            break

    # If curated catalog had fewer than batch_limit remaining, dynamically synthesize more feed topics
    if len(added_clusters) < batch_limit:
        needed = batch_limit - len(added_clusters)
        synthesized = _synthesize_feed_topics(
            query=payload.query or "",
            domain=dom_filter or None,
            existing_titles=existing_titles,
            count=needed,
            batch_seed=len(existing_titles)
        )
        for item in synthesized:
            t_low = item["topic_summary"].strip().lower()
            if t_low in existing_titles:
                continue
            nc = NarrativeCluster(
                topic_summary=item["topic_summary"],
                domain=item["domain"],
                key_phrases={"tokens": item["tokens"], "speakers": item["speakers"]},
                statement_count=item["statement_count"],
                unique_speakers_count=item["unique_speakers_count"],
                status=item["status"]
            )
            db.add(nc)
            db.commit()
            db.refresh(nc)
            existing_titles.add(t_low)
            added_clusters.append(_serialize_narrative(nc, db))

    all_clusters = db.query(NarrativeCluster).order_by(NarrativeCluster.statement_count.desc()).all()
    items_slice = [_serialize_narrative(c, db) for c in all_clusters[payload.offset: payload.offset + batch_limit]] or added_clusters

    return {
        "success": True,
        "added_count": len(added_clusters),
        "new_narratives": added_clusters,
        "items": items_slice,
        "total_count": len(all_clusters),
        "has_more": True
    }


@router.post("/narratives/search")
def search_or_generate_narratives(payload: SearchNarrativesRequest, db: Session = Depends(get_db)):
    """
    Search engine endpoint for 'Поиск тем для оценки':
    Finds all matching topics from the curated pool AND synthesizes multiple verifiable
    evaluation topics with AI analysis so any search query produces a full feed of topics.
    """
    q_raw = (payload.query or "").strip()
    dom_filter = (payload.domain or "").strip().lower()
    q_low = q_raw.lower().lstrip("#")

    existing_titles = {
        c.topic_summary.strip().lower()
        for c in db.query(NarrativeCluster).all()
    }

    added = []
    # 1. Pull matching curated evaluation topics
    for item in CURATED_EVALUATION_TOPICS:
        t_low = item["topic_summary"].strip().lower()
        if t_low in existing_titles:
            continue
        if dom_filter and item["domain"].lower() != dom_filter:
            continue
        if not q_low or (
            q_low in t_low
            or any(q_low in tok.lower() for tok in item.get("tokens", []))
            or any(q_low in sp.lower() for sp in item.get("speakers", []))
        ):
            nc = NarrativeCluster(
                topic_summary=item["topic_summary"],
                domain=item["domain"],
                key_phrases={"tokens": item["tokens"], "speakers": item["speakers"]},
                statement_count=item["statement_count"],
                unique_speakers_count=item["unique_speakers_count"],
                status=item["status"]
            )
            db.add(nc)
            db.commit()
            db.refresh(nc)
            existing_titles.add(t_low)
            added.append(_serialize_narrative(nc, db))
            if not q_low and len(added) >= 8:
                break

    # 2. Check existing clusters matching the query
    all_existing = db.query(NarrativeCluster).all()
    matching_existing = [
        c for c in all_existing
        if (not dom_filter or (c.domain or "").lower() == dom_filter)
        and (
            not q_low
            or q_low in c.topic_summary.lower()
            or any(q_low in str(tok).lower() for tok in (c.key_phrases or {}).get("tokens", []))
        )
    ]

    # 3. Ensure at least 6 matching topics exist for any query by synthesizing a feed batch
    if len(matching_existing) < 6:
        needed = max(4, 6 - len(matching_existing))
        synthesized = _synthesize_feed_topics(
            query=q_raw,
            domain=dom_filter or None,
            existing_titles=existing_titles,
            count=needed,
            batch_seed=len(existing_titles)
        )
        for item in synthesized:
            t_low = item["topic_summary"].strip().lower()
            if t_low in existing_titles:
                continue
            nc = NarrativeCluster(
                topic_summary=item["topic_summary"],
                domain=item["domain"],
                key_phrases={"tokens": item["tokens"], "speakers": item["speakers"]},
                statement_count=item["statement_count"],
                unique_speakers_count=item["unique_speakers_count"],
                status=item["status"]
            )
            db.add(nc)
            db.commit()
            db.refresh(nc)
            existing_titles.add(t_low)
            added.append(_serialize_narrative(nc, db))
            matching_existing.append(nc)

    return {
        "success": True,
        "query": q_raw,
        "matched_count": len(matching_existing),
        "added_count": len(added),
        "new_narratives": added
    }

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
