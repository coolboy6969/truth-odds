import re
from typing import Optional, Dict, Any, List
from sqlalchemy.orm import Session
from app.models.entities import Event, Speaker, Statement
from app.services.prediction_service import PredictionService

class AutoEventAnalysisEngine:
    """
    Automated event analyzer and Bayesian probability forecaster.
    When an event or topic is added:
    1. Refines domain (crypto, macro, tech, general) and deadline if mentioned.
    2. Attaches relevant forecasters (from user search or automated domain experts).
    3. Calculates Bayesian consensus probability based on expert credibility weights.
    """

    KNOWN_EXPERT_STANCES = {
        "crypto": [
            {
                "name": "Michael Saylor",
                "handle": "@saylor",
                "bio": "Основатель MicroStrategy, ведущий биткоин-стратег",
                "keywords": ["биткоин", "btc", "bitcoin", "крипто", "халвинг", "etf", "рынок"],
                "confidence": 0.90,
                "quote_template": "Институциональный дефицит предложения и ETF вызовут масштабный восходящий тренд."
            },
            {
                "name": "Arthur Hayes",
                "handle": "@CryptoHayes",
                "bio": "Основатель Maelstrom, сооснователь BitMEX, макро-стратег",
                "keywords": ["биткоин", "btc", "крипто", "solana", "солана", "ликвидность", "фрс", "рынок"],
                "confidence": 0.80,
                "quote_template": "Глобальное смягчение монетарной политики неизбежно направит избыточную фиатную ликвидность в активы."
            },
            {
                "name": "Vitalik Buterin",
                "handle": "@VitalikButerin",
                "bio": "Сооснователь Ethereum, блокчейн-исследователь",
                "keywords": ["эфириум", "eth", "ethereum", "l2", "смарт-контракт", "pos", "danksharding"],
                "confidence": 0.88,
                "quote_template": "Технологическая архитектура и масштабирование подтверждают устойчивость экосистемы."
            },
            {
                "name": "Peter Schiff",
                "handle": "@PeterSchiff",
                "bio": "Главный экономист Euro Pacific Capital, криптоскептик",
                "keywords": ["биткоин", "btc", "крипто", "криптовалют", "ethereum", "рынок"],
                "confidence": 0.12,
                "quote_template": "Спекулятивный пузырь не имеет реального фундаментального обеспечения и рухнет."
            }
        ],
        "macro": [
            {
                "name": "Arthur Hayes",
                "handle": "@CryptoHayes",
                "bio": "Макроэкономический аналитик, основатель Maelstrom",
                "keywords": ["ставка", "фрс", "инфляция", "доллар", "ликвидность", "кризис", "рецессия"],
                "confidence": 0.78,
                "quote_template": "Центральные банки вынуждены возобновить печать денег для покрытия дефицитов."
            },
            {
                "name": "Peter Schiff",
                "handle": "@PeterSchiff",
                "bio": "Главный экономист Euro Pacific Capital",
                "keywords": ["инфляция", "доллар", "рецессия", "кризис", "золото", "долг"],
                "confidence": 0.85,
                "quote_template": "Долговой кризис и падение покупательной способности доллара неизбежны."
            }
        ],
        "tech": [
            {
                "name": "Elon Musk",
                "handle": "@elonmusk",
                "bio": "CEO Tesla, xAI, SpaceX",
                "keywords": ["ai", "agi", "ии", "интеллект", "нейросеть", "робот", "технологии"],
                "confidence": 0.85,
                "quote_template": "Темпы прогресса моделей ИИ опережают любые прогнозы, превосходство над человеком близко."
            },
            {
                "name": "Vitalik Buterin",
                "handle": "@VitalikButerin",
                "bio": "Исследователь блокчейна и криптографии",
                "keywords": ["ai", "децентрализация", "технологии", "код"],
                "confidence": 0.70,
                "quote_template": "Открытые децентрализованные протоколы обеспечат надежный баланс в эпоху сверхинтеллекта."
            }
        ]
    }

    @classmethod
    def infer_domain(cls, title: str) -> str:
        t = title.lower()
        crypto_keywords = [
            "биткоин", "btc", "bitcoin", "эфириум", "eth", "ethereum", "solana", "солана",
            "крипто", "криптовалют", "etf", "халвинг", "альткоин", "дефи", "defi", "блокчейн",
            "токен", "xrp", "ripple", "binance", "bnb", "usdt", "стейблкоин", "майнинг"
        ]
        tech_keywords = [
            "ai", "agi", "ии", "интеллект", "нейросеть", "нейросети", "gpt", "openai", "claude",
            "deepseek", "tesla", "робот", "робототехник", "apple", "microsoft", "google", "meta",
            "nvidia", "чип", "чипы", "полупроводник", "софт", "квантов", "космос", "spacex", "стартап"
        ]
        macro_keywords = [
            "рецессия", "инфляция", "фрс", "доллар", "ввп", "ставка", "s&p", "s&p500", "nasdaq",
            "акций", "акции", "фондовый", "рынок", "кризис", "экономик", "госдолг", "долг",
            "облигаци", "золото", "нефть", "центробанк", "цб", "безработиц", "выборы", "президент", "трамп"
        ]

        # Prioritize domain by matching keywords
        if any(w in t for w in crypto_keywords):
            return "crypto"
        elif any(w in t for w in tech_keywords):
            return "tech"
        elif any(w in t for w in macro_keywords):
            return "macro"
        return "general"

    @classmethod
    def analyze_and_forecast_event(
        cls,
        db: Session,
        event: Event,
        speaker_name: Optional[str] = None,
        speaker_confidence: Optional[float] = None
    ) -> Event:
        """
        Runs automated semantic analysis, links or creates expert forecasters,
        records their predictions, and computes the Bayesian aggregated probability.
        """
        # 1. Refine domain automatically based on title semantics
        inferred = cls.infer_domain(event.title)
        if event.domain in ("auto", "general"):
            event.domain = inferred
        elif event.domain == "crypto" and inferred in ("tech", "macro"):
            event.domain = inferred

        # 2. If a specific speaker was searched/specified by the user
        if speaker_name and speaker_name.strip():
            s_clean = speaker_name.strip()
            conf = speaker_confidence if speaker_confidence is not None else 0.75
            PredictionService.record_statement(
                db=db,
                speaker_name=s_clean,
                event_title=event.title,
                speaker_confidence=conf,
                raw_quote=f"Прогноз аналитика {s_clean} по теме «{event.title}»",
                source_url="https://truthodds.local/forecast",
                source_platform="analysis",
                event_domain=event.domain,
                base_rate=event.base_rate
            )

        # 3. Automated expert matching: find matching domain figures
        title_lower = event.title.lower()
        domain_experts = cls.KNOWN_EXPERT_STANCES.get(event.domain, [])

        statements_added = 0
        for exp in domain_experts:
            # Check if expert keywords match title or if domain is a direct fit
            keyword_match = any(kw in title_lower for kw in exp["keywords"])
            if keyword_match or statements_added < 2:
                # Check if statement already exists
                existing = db.query(Statement).filter(
                    Statement.event_id == event.id
                ).all()
                existing_names = [
                    db.query(Speaker).filter(Speaker.id == s.speaker_id).first().name
                    for s in existing if db.query(Speaker).filter(Speaker.id == s.speaker_id).first()
                ]
                
                if exp["name"] not in existing_names:
                    PredictionService.record_statement(
                        db=db,
                        speaker_name=exp["name"],
                        speaker_handle=exp["handle"],
                        event_title=event.title,
                        speaker_confidence=exp["confidence"],
                        raw_quote=f"{exp['name']}: «{exp['quote_template']}»",
                        source_url="https://truthodds.local/expert_analysis",
                        source_platform="social",
                        event_domain=event.domain,
                        base_rate=event.base_rate
                    )
                    statements_added += 1

        db.refresh(event)
        return event
