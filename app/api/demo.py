from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from app.database.session import get_db
from app.models.entities import Speaker, Event, Statement
from app.engine.resolution import ResolutionEngine
from app.services.prediction_service import PredictionService

router = APIRouter(prefix="/api/demo", tags=["Demo & Seeding"])

@router.post("/seed")
def seed_demo_data(db: Session = Depends(get_db)):
    """
    Seeds realistic historical forecasters, resolved events, and active events
    to showcase how the truthfulness rating works in action.
    """
    # Check if already seeded
    if db.query(Speaker).count() > 0:
        return {"message": "Data already seeded", "speakers_count": db.query(Speaker).count()}

    # 1. Historical Resolved Events (to establish track records)
    ev_btc_etf = Event(
        title="Одобрение спотового Bitcoin ETF в США комиссией SEC",
        domain="crypto",
        base_rate=0.5,
        current_probability=1.0,
        status="RESOLVED_TRUE",
        resolution_notes="SEC одобрила 11 спотовых Bitcoin ETF в январе 2024 года"
    )
    ev_us_recession_2023 = Event(
        title="Начало официальной рецессии в США в течение 2023 года",
        domain="macro",
        base_rate=0.5,
        current_probability=0.0,
        status="RESOLVED_FALSE",
        resolution_notes="NBER не зафиксировал рецессию, экономика США выросла"
    )
    ev_eth_pos = Event(
        title="Успешный переход Ethereum на Proof-of-Stake (The Merge)",
        domain="crypto",
        base_rate=0.5,
        current_probability=1.0,
        status="RESOLVED_TRUE",
        resolution_notes="The Merge успешно состоялся в сентябре 2022 года"
    )
    
    db.add_all([ev_btc_etf, ev_us_recession_2023, ev_eth_pos])
    db.commit()

    # 2. Speakers
    # Vitalik Buterin: high accuracy in crypto
    sp_vitalik = Speaker(
        name="Vitalik Buterin",
        handle_or_channel="@VitalikButerin",
        bio="Сооснователь Ethereum, исследователь блокчейна",
        overall_credibility=0.5
    )
    # Peter Schiff: consistently bearish on crypto and predicting imminent collapse
    sp_schiff = Speaker(
        name="Peter Schiff",
        handle_or_channel="@PeterSchiff",
        bio="Главный экономист Euro Pacific Capital, криптоскептик",
        overall_credibility=0.5
    )
    # Michael Saylor: ultra bullish on Bitcoin
    sp_saylor = Speaker(
        name="Michael Saylor",
        handle_or_channel="Saylor Academy / MicroStrategy",
        bio="Основатель MicroStrategy, биткоин-максималист",
        overall_credibility=0.5
    )
    # Elon Musk: tech visionary, aggressive timelines
    sp_musk = Speaker(
        name="Elon Musk",
        handle_or_channel="@elonmusk",
        bio="CEO Tesla, xAI, SpaceX, владелец X",
        overall_credibility=0.5
    )

    db.add_all([sp_vitalik, sp_schiff, sp_saylor, sp_musk])
    db.commit()

    # 3. Historical statements for calibration
    # Vitalik on Eth PoS: said 90% (Outcome: True -> BS = (0.9-1)^2 = 0.01)
    # Vitalik on ETF: said 75% (Outcome: True -> BS = (0.75-1)^2 = 0.06)
    st_v1 = Statement(speaker_id=sp_vitalik.id, event_id=ev_eth_pos.id, source_platform="twitter",
                      source_url="https://twitter.com/VitalikButerin", raw_quote="Переход на PoS готов к деплою",
                      speaker_confidence=0.92, speaker_weight_applied=0.5)
    st_v2 = Statement(speaker_id=sp_vitalik.id, event_id=ev_btc_etf.id, source_platform="interview",
                      source_url="https://youtube.com/watch?v=vitalik", raw_quote="Регуляторы неизбежно примут ETF",
                      speaker_confidence=0.80, speaker_weight_applied=0.5)

    # Peter Schiff:
    # Said BTC ETF will NOT be approved (confidence 0.10, Outcome: True -> BS = (0.1-1)^2 = 0.81!)
    # Said US recession in 2023 will definitely happen (confidence 0.95, Outcome: False -> BS = (0.95-0)^2 = 0.90!)
    st_s1 = Statement(speaker_id=sp_schiff.id, event_id=ev_btc_etf.id, source_platform="youtube",
                      source_url="https://youtube.com/watch?v=schiff", raw_quote="SEC никогда не одобрит пирамиду биткоина",
                      speaker_confidence=0.10, speaker_weight_applied=0.5)
    st_s2 = Statement(speaker_id=sp_schiff.id, event_id=ev_us_recession_2023.id, source_platform="youtube",
                      source_url="https://youtube.com/watch?v=schiff_crash", raw_quote="Крах экономики США в 2023 году неизбежен",
                      speaker_confidence=0.95, speaker_weight_applied=0.5)

    # Saylor on ETF: 95%
    st_sy1 = Statement(speaker_id=sp_saylor.id, event_id=ev_btc_etf.id, source_platform="youtube",
                       source_url="https://youtube.com/watch?v=saylor", raw_quote="Спотовый ETF будет одобрен институционалами",
                       speaker_confidence=0.95, speaker_weight_applied=0.5)

    db.add_all([st_v1, st_v2, st_s1, st_s2, st_sy1])
    db.commit()

    # Recalculate track records of all speakers based on resolved events!
    ResolutionEngine.recalculate_speaker_track_record(db, sp_vitalik.id)
    ResolutionEngine.recalculate_speaker_track_record(db, sp_schiff.id)
    ResolutionEngine.recalculate_speaker_track_record(db, sp_saylor.id)
    ResolutionEngine.recalculate_speaker_track_record(db, sp_musk.id)

    # 4. Now create ACTIVE Future Events
    ev_btc_150k = Event(
        title="Биткоин достигнет отметки $150,000 до конца 2026 года",
        domain="crypto",
        base_rate=0.5,
        current_probability=0.5,
        status="ACTIVE"
    )
    ev_agi_2026 = Event(
        title="Создание общепризнанного AGI (искусственного сверхинтеллекта) до конца 2026",
        domain="tech",
        base_rate=0.35,
        current_probability=0.35,
        status="ACTIVE"
    )
    db.add_all([ev_btc_150k, ev_agi_2026])
    db.commit()

    # Record predictions for active events:
    # Saylor says 90% BTC to $150k
    PredictionService.record_statement(
        db=db,
        speaker_name="Michael Saylor",
        event_title="Биткоин достигнет отметки $150,000 до конца 2026 года",
        speaker_confidence=0.90,
        raw_quote="Биткоин преодолеет $150,000 благодаря халвингу и ETF",
        source_url="https://youtube.com/watch?v=saylor_future",
        event_domain="crypto"
    )

    # Schiff says 10% BTC to $150k (because Schiff has terrible credibility, his negative statement won't drag it down much!)
    PredictionService.record_statement(
        db=db,
        speaker_name="Peter Schiff",
        event_title="Биткоин достигнет отметки $150,000 до конца 2026 года",
        speaker_confidence=0.08,
        raw_quote="Биткоин рухнет в ноль, никакого роста до 150к не будет",
        source_url="https://youtube.com/watch?v=schiff_bubble",
        event_domain="crypto"
    )

    # Elon Musk on AGI:
    PredictionService.record_statement(
        db=db,
        speaker_name="Elon Musk",
        event_title="Создание общепризнанного AGI (искусственного сверхинтеллекта) до конца 2026",
        speaker_confidence=0.85,
        raw_quote="Я думаю, что умнее любого человека AI станет уже в следующем году или к 2026",
        source_url="https://x.com/elonmusk",
        source_platform="twitter",
        event_domain="tech"
    )

    return {
        "success": True,
        "message": "Demo data successfully initialized with verified forecasters and events."
    }
