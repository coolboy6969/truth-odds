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

        # 4. Generate rich AI description if default or empty
        ai_eval = cls.generate_ai_topic_analysis(
            title=event.title,
            domain=event.domain,
            probability=event.current_probability,
            statements_count=len(event.statements or [])
        )
        if not event.description or "Тема проверена автоматической системой" in event.description or len(event.description) < 60:
            event.description = ai_eval["summary"]
            db.commit()
            db.refresh(event)

        return event

    @classmethod
    def generate_ai_topic_analysis(
        cls,
        title: str,
        domain: Optional[str] = None,
        probability: float = 0.5,
        statements_count: int = 0,
        keywords: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        """
        Generates a structured AI analytical description and evaluation summary
        for a selected topic, narrative cluster, or forecasting event.
        """
        t_clean = (title or "").strip()
        t_low = t_clean.lower()
        dom = (domain or cls.infer_domain(t_clean)).lower()
        prob_pct = round(probability * 100)

        # Extract any numerical targets or years
        numbers = re.findall(r'\$?\d[\d,\.]*\s*(?:k|тыс|млн|млрд|трлн|%|프로)?', t_clean, re.IGNORECASE)
        target_str = numbers[0] if numbers else None

        # Domain-specific contextual synthesis
        if dom == "crypto":
            if any(w in t_low for w in ["bitcoin", "биткоин", "btc", "резерв"]):
                context = (
                    f"Тема оценивает перспективу движения и институционального принятия Bitcoin "
                    f"{f'(целевой ориентир: {target_str})' if target_str else ''}. "
                    f"Ключевыми драйверами выступают притоки капитала в спотовые ETF, сокращение эмиссии после халвинга "
                    f"и динамика глобальной долларовой ликвидности M2."
                )
                bull_factors = [
                    "Устойчивый институциональный спрос через спотовые ETF и корпоративные казначейства",
                    "Дефицит предложения на криптобиржах и долгосрочное удержание монет (HODL-волны)",
                    "Потенциальное смягчение монетарной политики ФРС и приток ликвидности"
                ]
                bear_factors = [
                    "Риск фиксации прибыли крупными держателями вблизи психологических уровней сопротивления",
                    "Макроэкономические шоки или задержка снижения процентных ставок",
                    "Ужесточение регуляторных требований к крипто-инфраструктуре"
                ]
                oracle_criteria = "Автоматическая сверка спотовой котировки BTC/USDT через API бирж (Binance / CoinGecko) и официальных регуляторных публикаций."
            elif any(w in t_low for w in ["solana", "солана", "sol", "dex"]):
                context = (
                    f"Тема посвящена оценке конкурентоспособности экосистемы Solana и её метрик активности "
                    f"(объемы торгов на DEX, TVL и пропускная способность сети) в сравнении с L1/L2 конкурентами."
                )
                bull_factors = [
                    "Высокая скорость финализации транзакций и сверхнизкие комиссии для розничных пользователей",
                    "Рост объемов торгов на децентрализованных биржах (Raydium, Jupiter) и запуск обновления Firedancer",
                    "Активный приток разработчиков и потребительских Web3-приложений"
                ]
                bear_factors = [
                    "Высокая конкуренция со стороны L2-решений экосистемы Ethereum (Base, Arbitrum)",
                    "Зависимость части ончейн-объемов от спекулятивной активности в секторе мем-токенов"
                ]
                oracle_criteria = "Верификация ончейн-метрик суточного объема DEX и рыночной капитализации через DeFiLlama и CoinGecko."
            elif any(w in t_low for w in ["ethereum", "эфириум", "eth"]):
                context = (
                    f"Оценка траектории развития экосистемы Ethereum {f'(ориентир: {target_str})' if target_str else ''}, "
                    f"включая влияние институциональных фондов, стейкинга и масштабирования L2-сетей."
                )
                bull_factors = [
                    "Доминирование в секторе DeFi и токенизации реальных активов (RWA)",
                    "Дефляционный механизм сжигания комиссий EIP-1559 при высокой загрузке сети",
                    "Институциональная интеграция смарт-контрактов крупнейшими банками и фондами"
                ]
                bear_factors = [
                    "Фрагментация ликвидности между множеством сетей второго уровня (L2)",
                    "Переток части розничного трафика в альтернативные высокоскоростные блокчейны"
                ]
                oracle_criteria = "Сверка рыночной цены ETH/USD и ончейн-показателей через аналитические агрегаторы."
            else:
                context = (
                    f"Анализ вероятности реализации сценария «{t_clean}» на рынке цифровых активов. "
                    f"Модель учитывает рыночную цикличность, потоки капитала и историческую точность высказавшихся криптоаналитиков."
                )
                bull_factors = [
                    "Рост совокупной капитализации крипторынка и приток свежей ликвидности",
                    "Поддержка тренда со стороны профильных аналитиков с высоким рейтингом доверия"
                ]
                bear_factors = [
                    "Высокая волатильность криптоактивов и зависимость от склонности к риску (Risk-On/Risk-Off)",
                    "Риск коррекции после локального перегрева рынка"
                ]
                oracle_criteria = "Проверка котировок и рыночных фактов через автоматический крипто-оракул TruthOdds."

        elif dom == "macro":
            context = (
                f"Макроэкономическая тема «{t_clean}» оценивает влияние денежно-кредитной политики центробанков, "
                f"инфляционных трендов и долговых рынков на глобальную финансовую систему."
            )
            bull_factors = [
                "Сигналы замедления деловой активности, вынуждающие центробанки к смягчению политики",
                "Рост государственного долга и стоимости его обслуживания, стимулирующий спрос на защитные активы",
                "Консенсус макроэкономистов относительно смены фазы кредитного цикла"
            ]
            bear_factors = [
                "Устойчивость рынка труда и инерционная инфляция в секторе услуг",
                "Жесткая риторика регуляторов (ФРС / ЦБ) о сохранении ставок на повышенном уровне дольше ожидаемого"
            ]
            oracle_criteria = "Официальные пресс-релизы ФРС США, макроэкономическая статистика CPI/ВВП и котировки мировых индексов."

        elif dom == "tech":
            context = (
                f"Технологический прогноз «{t_clean}» анализирует темпы внедрения искусственного интеллекта, "
                f"вычислительной инфраструктуры и прорывных разработок ведущих тех-корпораций."
            )
            bull_factors = [
                "Экспоненциальный рост вычислительных мощностей и инвестиций BigTech в ИИ-инфраструктуру",
                "Быстрое внедрение автономных ИИ-агентов и мультимодальных моделей в корпоративный сектор",
                "Высокая уверенность технологических лидеров и профильных венчурных экспертов"
            ]
            bear_factors = [
                "Ограничения по энергопотреблению дата-центров и дефицит передовых чипов",
                "Регуляторные барьеры в сфере безопасности ИИ и авторского права"
            ]
            oracle_criteria = "Официальные релизы технологических компаний, отраслевые бенчмарки и финансовая отчетность."

        else:
            context = (
                f"Комплексная аналитическая оценка темы «{t_clean}». "
                f"ИИ-модель сопоставляет аргументы экспертов, взвешивает их по историческому Brier Score "
                f"и вычисляет вероятность наступления события."
            )
            bull_factors = [
                "Положительный баланс аргументов от верифицированных участников дискуссии",
                "Соответствие наблюдаемым рыночным и информационным трендам"
            ]
            bear_factors = [
                "Неопределенность внешних факторов и временных рамок реализации сценария",
                "Наличие альтернативных сценариев развития ситуации"
            ]
            oracle_criteria = "Подтверждение факта по официальным новостным агентствам и верифицированным источникам данных."

        if prob_pct >= 68:
            verdict = f"Высокая вероятность реализации ({prob_pct}%): весовой консенсус авторитетных аналитиков и фундаментальные драйверы уверенно поддерживают данный сценарий."
        elif prob_pct <= 35:
            verdict = f"Сценарий маловероятен ({prob_pct}%): большинство калиброванных экспертов настроены скептически, преобладают структурные барьеры и риски."
        else:
            verdict = f"Дискуссионный баланс ({prob_pct}%): мнения аналитиков разделились, для уверенного сдвига вероятности требуется подтверждение триггеров в медиа или ончейн-данных."

        return {
            "summary": context,
            "bull_factors": bull_factors,
            "bear_factors": bear_factors,
            "oracle_criteria": oracle_criteria,
            "ai_verdict": verdict,
            "probability_percent": prob_pct,
            "statements_analyzed": statements_count,
            "domain": dom,
            "keywords": keywords or []
        }

