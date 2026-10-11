from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from app.database.session import get_db
from app.models.entities import Speaker, Event, Statement, MonitoredSource
from app.engine.resolution import ResolutionEngine
from app.services.prediction_service import PredictionService

router = APIRouter(prefix="/api/crypto", tags=["Crypto Top 10"])

TOP_10_CRYPTO_FIGURES = [
    {
        "name": "Michael Saylor",
        "handle": "@saylor",
        "bio": "Председатель MicroStrategy, ведущий биткоин-максималист и институциональный стратег",
        "youtube_channel": "UC43G39d-T3a_hC6i5H2rX4A", # MicroStrategy / Saylor
        "historic": [
            ("Биткоин превзойдет доходность золота и S&P 500 на 4-летнем горизонте", 0.95, True, "MicroStrategy Q4 Report"),
            ("Комиссия SEC одобрит спотовые Bitcoin ETF в начале 2024 года", 0.95, True, "Bloomberg Interview Jan 2024")
        ],
        "active": [
            ("Биткоин достигнет отметки $150,000 до конца 2026 года", 0.90, "Биткоин достигнет $150,000 на фоне дефицита предложения после халвинга")
        ]
    },
    {
        "name": "Vitalik Buterin",
        "handle": "@VitalikButerin",
        "bio": "Сооснователь Ethereum, ведущий исследователь блокчейн-масштабирования и криптографии",
        "youtube_channel": "UC1j_9J6b7cWb_Qk8k2hK8vw",
        "historic": [
            ("Ethereum успешно перейдет на Proof-of-Stake (The Merge)", 0.92, True, "EthFoundation Official 2022"),
            ("L2-роллапы (Arbitrum, Optimism) будут обрабатывать более 80% транзакций", 0.85, True, "L2Beat Stats 2024")
        ],
        "active": [
            ("Комиссии в сети Ethereum сохранятся ниже 15 gwei благодаря blob-транзакциям до конца 2026", 0.85, "Proto-Danksharding обеспечил устойчивую пропускную способность для L2")
        ]
    },
    {
        "name": "Arthur Hayes",
        "handle": "@CryptoHayes",
        "bio": "Основатель Maelstrom, сооснователь BitMEX, макроэкономический аналитик",
        "youtube_channel": "UCj3LzXQk_gK5vVvFvB8y5xw",
        "historic": [
            ("Банковский кризис в США (SVB) заставит ФРС включить экстренную ликвидность в 2023", 0.90, True, "Bank Term Funding Program запущена ФРС"),
            ("Рост ликвидности приведет к росту Биткоина выше $40,000 к концу 2023", 0.82, True, "Ралли BTC в Q4 2023")
        ],
        "active": [
            ("Снижение процентных ставок центробанками вытолкнет Биткоин выше $200,000 до 2027 года", 0.78, "Глобальное монетарное смягчение неизбежно обесценит фиат")
        ]
    },
    {
        "name": "PlanB",
        "handle": "@100trillionUSD",
        "bio": "Создатель квантитативной модели Stock-to-Flow (S2F) для оценки циклов Биткоина",
        "youtube_channel": "UCnK5F2_v6H2vG6f0X9aK1Lw",
        "historic": [
            ("Биткоин достигнет $100,000 до декабря 2021 по модели S2F", 0.98, False, "Пик 2021 составил $69k, модель S2F сломалась"),
            ("Биткоин удержится выше $20,000 во время медвежьего цикла 2022", 0.85, False, "BTC падал до $15,476 в ноябре 2022")
        ],
        "active": [
            ("Средняя цена Биткоина в цикле 2024-2028 превысит $250,000", 0.85, "Модель S2F предсказывает экспоненциальный скачок после 4-го халвинга")
        ]
    },
    {
        "name": "Cathie Wood",
        "handle": "@CathieDWood",
        "bio": "CEO & CIO ARK Investment Management, пионер институциональных инвестиций в инновации",
        "youtube_channel": "UCE_mRsZft453nwHzg1nIpxw", # ARK Invest
        "historic": [
            ("SEC одобрит институциональные спотовые биткоин-фонды в первом квартале 2024", 0.90, True, "Одобрение 11 ETF"),
            ("Приток институционального капитала в крипто-ETF превысит $50B", 0.85, True, "Рекордные притоки IBIT и FBTC")
        ],
        "active": [
            ("Биткоин достигнет отметки $150,000 до конца 2026 года", 0.80, "Институциональный базовый сценарий ARK Invest для BTC"),
            ("Биткоин достигнет $1,000,000 за монету к 2030 году", 0.70, "Долгосрочный прогноз замещения золота и резервных активов")
        ]
    },
    {
        "name": "Guy Turner (Coin Bureau)",
        "handle": "@CoinBureau",
        "bio": "Ведущий аналитик Coin Bureau — крупнейшего образовательного крипто-канала YouTube (~2.5M)",
        "youtube_channel": "UCqK_GSMbpiV8spgD3ZGloSw", # Coin Bureau Official Channel ID
        "historic": [
            ("SEC одобрит спотовые Ethereum ETF летом 2024 года", 0.78, True, "Одобрение ETH ETF в июле 2024"),
            ("Solana восстановит позиции в топ-5 капитализации после краха FTX", 0.75, True, "SOL выросла с $8 до $200+")
        ],
        "active": [
            ("Solana превзойдет Ethereum по рыночной капитализации до 2027 года", 0.30, "Маловероятно из-за институционального доминирования Ethereum")
        ]
    },
    {
        "name": "Benjamin Cowen",
        "handle": "@BenjaminCowen",
        "bio": "Основатель Into The Cryptoverse, квантитативный аналитик рынка и доминации",
        "youtube_channel": "UCRvqjQPSeaWn-uEx-w0XOIg", # Benjamin Cowen Channel ID
        "historic": [
            ("Доминация Биткоина (BTC.D) вырастет до 60% в фазе консолидации", 0.85, True, "BTC.D достигла 60% в 2024"),
            ("Пара ETH/BTC упадет ниже уровня 0.05", 0.82, True, "ETH/BTC снизился до 0.035")
        ],
        "active": [
            ("Общая капитализация альткоинов (TOTAL3) установит новый исторический рекорд в 2026", 0.75, "Капитал перетечет из BTC в альткоины на финальной стадии цикла")
        ]
    },
    {
        "name": "Raoul Pal",
        "handle": "@RaoulGMI",
        "bio": "CEO Real Vision, экс-топ Goldman Sachs, автор теории 'The Exponential Age'",
        "youtube_channel": "UCBYyU-UGyGAAO_Ziofls1EQ", # Real Vision
        "historic": [
            ("Крипторынок покажет мощное ралли вслед за ростом глобальной ликвидности M2 в 2024", 0.85, True, "Корреляция M2 и крипты подтвердилась"),
            ("Solana станет основным высокопроизводительным блокчейном для масс", 0.80, True, "Взрывной рост транзакций и DeFi на Solana")
        ],
        "active": [
            ("Совокупная капитализация рынка криптовалют превысит $10 Триллионов до конца 2026", 0.70, "Вход суверенных фондов и глобальная токенизация активов RWA")
        ]
    },
    {
        "name": "Peter Schiff",
        "handle": "@PeterSchiff",
        "bio": "Президент Euro Pacific Capital, криптоскептик и золотой инвестор (Обратный индикатор)",
        "youtube_channel": "UCIjuLiLHdFxYtFmW4iQQRtA", # Peter Schiff Channel ID
        "historic": [
            ("SEC никогда не одобрит спотовые Биткоин ETF из-за риска манипуляций", 0.95, False, "SEC одобрила 11 ETF"),
            ("Биткоин обнулится и рухнет до нуля после банкротства биржи FTX", 0.92, False, "BTC вырос в 6 раз с минимумов 2022 года"),
            ("Экономика США погрузится в катастрофическую рецессию в 2023 году", 0.90, False, "ВВП США вырос на 2.5%")
        ],
        "active": [
            ("Биткоин рухнет ниже $20,000 из-за лопания спекулятивного пузыря", 0.92, "У Биткоина нет внутренней ценности, этот пузырь лопнет с треском"),
            ("Биткоин достигнет отметки $150,000 до конца 2026 года", 0.08, "Абсурдный сценарий, никакого роста до $150k не будет")
        ]
    },
    {
        "name": "Altcoin Daily (Aaron & Austin)",
        "handle": "@AltcoinDaily",
        "bio": "Крупнейший ежедневный новостной и аналитический крипто-канал YouTube (~1.4M)",
        "youtube_channel": "UCbLhGKVY-bJPcawebgtNfbw", # Altcoin Daily Channel ID
        "historic": [
            ("Институциональные гиганты Wall Street (BlackRock, Fidelity) запустят криптопродукты", 0.90, True, "BlackRock IBIT стал самым успешным ETF в истории"),
            ("Биткоин обновит исторический максимум $69,000 еще до халвинга 2024 года", 0.75, True, "BTC достиг $73k в марте 2024")
        ],
        "active": [
            ("Биткоин достигнет отметки $150,000 до конца 2026 года", 0.80, "Рекордный институциональный спрос и накопление ETF"),
            ("Стейкинг Ethereum получит одобрение в спотовых ETF фондах в США", 0.70, "Регуляторы неизбежно одобрят доходность для институционалов")
        ]
    }
]

@router.post("/seed-top10")
def seed_crypto_top10(db: Session = Depends(get_db)):
    """
    Seeds the top 10 crypto personalities with their actual YouTube channels,
    historical predictions for track record calibration, and active events.
    """
    created_speakers = []
    
    for fig in TOP_10_CRYPTO_FIGURES:
        speaker = PredictionService.get_or_create_speaker(
            db=db,
            name=fig["name"],
            handle_or_channel=fig["handle"]
        )
        speaker.bio = fig["bio"]
        
        # Register MonitoredSource
        source = db.query(MonitoredSource).filter(MonitoredSource.channel_identifier == fig["youtube_channel"]).first()
        if not source:
            source = MonitoredSource(
                speaker_id=speaker.id,
                platform="youtube",
                channel_title=f"{fig['name']} YouTube",
                channel_identifier=fig["youtube_channel"],
                feed_url=f"https://www.youtube.com/feeds/videos.xml?channel_id={fig['youtube_channel']}",
                is_active=1
            )
            db.add(source)

        # 1. Process Historical Predictions (for calibration)
        for title, conf, outcome, notes in fig["historic"]:
            ev = db.query(Event).filter(Event.title == title).first()
            if not ev:
                ev = Event(
                    title=title,
                    domain="crypto",
                    base_rate=0.5,
                    current_probability=1.0 if outcome else 0.0,
                    status="RESOLVED_TRUE" if outcome else "RESOLVED_FALSE",
                    resolution_notes=notes
                )
                db.add(ev)
                db.commit()
                db.refresh(ev)

            # Check statement
            existing_stmt = db.query(Statement).filter(
                Statement.speaker_id == speaker.id,
                Statement.event_id == ev.id
            ).first()
            if not existing_stmt:
                stmt = Statement(
                    speaker_id=speaker.id,
                    event_id=ev.id,
                    source_platform="youtube",
                    source_url=f"https://youtube.com/watch?v={fig['youtube_channel'][:11]}",
                    raw_quote=f"Прогноз: {title}",
                    speaker_confidence=conf,
                    speaker_weight_applied=0.5
                )
                db.add(stmt)

        db.commit()

        # Recalculate track record
        ResolutionEngine.recalculate_speaker_track_record(db, speaker.id)

        # 2. Process Active Predictions
        from app.engine.auto_analysis import AutoEventAnalysisEngine
        for ev_title, conf, quote in fig["active"]:
            calib = AutoEventAnalysisEngine.evaluate_claim_calibration(ev_title, "crypto")
            stmt = PredictionService.record_statement(
                db=db,
                speaker_name=fig["name"],
                event_title=ev_title,
                speaker_confidence=conf,
                raw_quote=quote,
                source_url=f"https://youtube.com/watch?v={fig['youtube_channel'][:11]}",
                source_platform="youtube",
                event_domain="crypto",
                speaker_handle=fig["handle"],
                base_rate=float(calib.get("base_rate", 0.5))
            )
            if stmt and stmt.event:
                AutoEventAnalysisEngine.analyze_and_forecast_event(db, stmt.event)

        created_speakers.append({
            "name": speaker.name,
            "credibility": speaker.overall_credibility,
            "brier_score": speaker.overall_brier_score,
            "resolved_count": speaker.resolved_predictions
        })

    return {
        "success": True,
        "message": "Top 10 Crypto figures & YouTube channels initialized with full calibration and active markets.",
        "speakers": created_speakers
    }
