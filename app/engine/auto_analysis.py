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
            "биткоин", "биткойн", "btc", "bitcoin", "эфириум", "eth", "ethereum", "solana", "солана",
            "крипто", "криптовалют", "etf", "халвинг", "альткоин", "дефи", "defi", "блокчейн",
            "токен", "xrp", "ripple", "binance", "bnb", "usdt", "стейблкоин", "майнинг", "tron", "trx"
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
    def is_bearish_or_negated_claim(cls, title: str) -> bool:
        t_low = (title or "").lower()
        return bool(
            re.search(
                r'\bне\s+(?:войдет|станет|попадет|будет|окажется|удержится|сможет|входит|достигнет|превысит|пробьет|вырастет|поднимется)\b',
                t_low,
            )
            or any(
                w in t_low
                for w in ["упадет", "рухнет", "обвалится", "снизится ниже", "падение ниже", "крах", "пузырь", "вылетит из"]
            )
        )

    @classmethod
    def recalculate_event_probability(cls, db: Session, event: Event) -> Event:
        from app.engine.scoring import ForecasterScorer
        all_stmts = db.query(Statement).filter(Statement.event_id == event.id).all()
        if not all_stmts:
            event.current_probability = event.base_rate
            db.commit()
            return event
        stmt_dicts = []
        for s in all_stmts:
            sp = db.query(Speaker).filter(Speaker.id == s.speaker_id).first()
            sp_weight = PredictionService.get_speaker_weight_for_domain(sp, event.domain) if sp else s.speaker_weight_applied
            stmt_dicts.append({
                "speaker_confidence": s.speaker_confidence,
                "speaker_weight": sp_weight,
            })
        event.current_probability = ForecasterScorer.aggregate_event_probability(stmt_dicts, event.base_rate)
        db.commit()
        db.refresh(event)
        return event

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

        # 3. Automated expert matching: find matching domain figures (with polarity/negation awareness)
        title_lower = event.title.lower()
        is_neg_or_bearish = cls.is_bearish_or_negated_claim(event.title)
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
                    base_conf = exp["confidence"]
                    quote_text = exp["quote_template"]
                    if is_neg_or_bearish and event.domain in ("crypto", "tech"):
                        base_conf = round(1.0 - base_conf, 2)
                        if base_conf < 0.5:
                            quote_text = "Фундаментальная капитализация и институциональный спрос опровергают данный негативный сценарий."

                    PredictionService.record_statement(
                        db=db,
                        speaker_name=exp["name"],
                        speaker_handle=exp["handle"],
                        event_title=event.title,
                        speaker_confidence=base_conf,
                        raw_quote=f"{exp['name']}: «{quote_text}»",
                        source_url="https://truthodds.local/expert_analysis",
                        source_platform="social",
                        event_domain=event.domain,
                        base_rate=event.base_rate
                    )
                    statements_added += 1

        db.refresh(event)

        # 4. Generate concrete hypothesis description
        ai_eval = cls.generate_ai_topic_analysis(
            title=event.title,
            domain=event.domain,
            probability=event.current_probability,
            statements_count=len(event.statements or []),
            statements=event.statements
        )
        if cls.is_boilerplate_description(event.description):
            event.description = ai_eval["summary"]
            db.commit()
            db.refresh(event)

        return event

    GENERIC_AUTO_QUOTES = (
        "Институциональный дефицит предложения и ETF вызовут масштабный восходящий тренд",
        "Глобальное смягчение монетарной политики неизбежно направит избыточную фиатную ликвидность в активы",
        "Технологическая архитектура и масштабирование подтверждают устойчивость экосистемы",
        "Спекулятивный пузырь не имеет реального фундаментального обеспечения и рухнет",
        "Фундаментальная капитализация и институциональный спрос опровергают данный негативный сценарий",
        "Фундаментальная капитализация актива уверенно удерживает его в элите мирового рынка",
        "Центральные банки вынуждены возобновить печать денег для покрытия дефицитов",
        "Долговой кризис и падение покупательной способности доллара неизбежны",
        "Темпы прогресса моделей ИИ опережают любые прогнозы",
        "Открытые децентрализованные протоколы обеспечат надежный баланс",
        "Прогноз аналитика ",
    )

    @classmethod
    def is_boilerplate_description(cls, desc: Optional[str]) -> bool:
        if not desc or len(desc.strip()) < 35:
            return True
        d_low = desc.lower()
        boilerplate_markers = (
            "комплексная аналитическая оценка темы",
            "ии-модель сопоставляет аргументы",
            "анализ вероятности реализации сценария",
            "тема оценивает перспективу движения",
            "макроэкономическая тема «",
            "технологический прогноз «",
            "тема проверена автоматической системой",
            "тема посвящена оценке конкурентоспособности",
            "оценка траектории развития экосистемы",
        )
        return any(m in d_low for m in boilerplate_markers)

    @classmethod
    def clean_event_title(cls, title: str) -> str:
        t = (title or "").replace("\xa0", " ").strip()
        # Strip trailing publisher after spaces/tabs
        t = re.sub(r'\s{2,}[A-Za-zА-Яа-яЁё0-9\.\-\s]{2,25}$', '', t).strip()
        # If title contains a duplicated sentence "Sentence A. Sentence A...", keep only the first clean sentence
        parts = [p.strip() for p in re.split(r'\.\s+', t) if p.strip()]
        if len(parts) >= 2:
            p0_low = parts[0].lower()
            p1_low = parts[1].lower()
            if p1_low.startswith(p0_low[:25]) or p0_low.startswith(p1_low[:25]):
                t = parts[0]
        # Strip trailing " – Ин-Спейс" or similar media source suffix if duplicated
        t = re.sub(r'\s+[–—-]\s+(?:Ин-Спейс|ForkLog|Bits Media|Yellow\.com|РБК|Коммерсантъ)\s*$', '', t, flags=re.IGNORECASE).strip()
        return t

    @classmethod
    def _extract_substantive_thesis(cls, title: str, statements: Optional[List[Any]]) -> Optional[str]:
        if not statements:
            return None
        t_norm = re.sub(r'\W+', '', (title or "").lower())
        for st in statements:
            raw_q = st.get("raw_quote") if isinstance(st, dict) else getattr(st, "raw_quote", "")
            if not raw_q:
                continue
            q_clean = raw_q.replace("\xa0", " ").strip()
            # Remove leading "Speaker Name: «...»" wrapper if present
            m = re.match(r'^[^:]{2,40}:\s*[«"](.+)[»"]$', q_clean)
            if m:
                q_clean = m.group(1).strip()
            q_clean = q_clean.strip('«»"')
            if any(g.lower() in q_clean.lower() for g in cls.GENERIC_AUTO_QUOTES):
                continue
            q_norm = re.sub(r'\W+', '', q_clean.lower())
            if not q_norm or q_norm == t_norm or q_norm.startswith(t_norm[:30]) or t_norm.startswith(q_norm[:30]):
                continue
            if len(q_clean) >= 35:
                return q_clean
        return None

    @classmethod
    def build_hypothesis_description(
        cls,
        title: str,
        domain: str = "general",
        statements: Optional[List[Any]] = None
    ) -> str:
        """
        Builds a concrete, informative description of the event's hypothesis/assumption
        (суть предположения и условие его выполнения) without repeating the title or adding meta-fluff.
        """
        t_clean = cls.clean_event_title(title)
        t_low = t_clean.lower()
        dom = (domain or cls.infer_domain(t_clean)).lower()
        is_neg = cls.is_bearish_or_negated_claim(t_clean)
        thesis = cls._extract_substantive_thesis(t_clean, statements)

        # 1. Global Asset Ranking hypothesis (e.g. "биткоин не войдет в топ 10 активов 2025 года")
        rank_match = re.search(r'(?:топ|top)[\s\-]*(\d{1,4})', t_low)
        if rank_match and any(w in t_low for w in ["актив", "asset", "капитализац", "биткоин", "bitcoin", "btc"]):
            rank_n = int(rank_match.group(1))
            year_m = re.search(r'\b(202\d)\b', t_low)
            year_str = f" по итогам {year_m.group(1)} года" if year_m else ""
            if is_neg:
                return (
                    f"Предполагается, что{year_str} рыночная капитализация Bitcoin уступит крупнейшим мировым корпорациям и драгоценным металлам, "
                    f"в результате чего актив выбудет из Топ-{rank_n} мирового рейтинга. "
                    f"Условие выполняется только при падении капитализации BTC ниже порога {rank_n}-го места в мире."
                )
            return (
                f"Предполагается, что{year_str} рыночная капитализация Bitcoin позволит ему занять и удерживать место в Топ-{rank_n} "
                f"крупнейших мировых активов наряду с золотом и ведущими технологическими корпорациями."
            )

        # 2. Explicit price target hypothesis (e.g. "$150,000", "ниже 10 долларов", "не достигнет $200 000")
        price_match = re.search(
            r'(\$\s*\d[\d\s,\.]*(?:k|тыс|млн|млрд)?|\d[\d\s,\.]*\s*(?:доллар\w*|usd|тыс\w*\s*доллар\w*))',
            t_clean,
            re.IGNORECASE,
        )
        if price_match and any(w in t_low for w in ["биткоин", "биткойн", "bitcoin", "btc", "eth", "ethereum", "эфириум", "solana", "солана", "sol", "золот", "gold", "достигнет", "превысит", "ниже", "выше", "курс", "цена"]):
            target_raw = re.sub(r'\s+', ' ', price_match.group(1).strip())
            year_m = re.search(r'(?:до|к концу|в)\s+(202\d)\s*(?:год\w*|г\.)?', t_low)
            horizon_str = f" в горизонте {year_m.group(0)}" if year_m else ""
            if re.search(r'\bне\s+(?:достигнет|превысит|пробьет|поднимется|возьмет)\b', t_low):
                return (
                    f"Предполагается, что котировка актива столкнется с циклическим сопротивлением и замедлением притока капитала, "
                    f"из-за чего рыночная цена не сможет преодолеть отметку {target_raw}{horizon_str}. "
                    f"Предположение подтверждается, если максимум цены останется ниже указанного уровня."
                )
            if any(w in t_low for w in ["ниже", "упадет", "рухнет", "обвалится", "снизится"]):
                return (
                    f"Предполагается сценарий глубокого снижения спотовой цены актива ниже отметки {target_raw}{horizon_str} "
                    f"вследствие оттока ликвидности или макроэкономического шока. "
                    f"Условие считается выполненным при фиксации рыночного курса ниже целевого порога."
                )
            if thesis:
                return f"Предполагается рост рыночной котировки актива выше целевого рубежа {target_raw}{horizon_str}. Ключевой тезис: {thesis}"
            return (
                f"Предполагается устойчивый рост спотовой цены актива и закрепление выше отметки {target_raw}{horizon_str} "
                f"за счет институционального спроса, притока ликвидности и сокращения доступного биржевого предложения."
            )

        # 3. Specific News / Special Topics (Einstein, Strategy ChatGPT, Ethereum Foundation, Tron Post-Quantum, Altcoins Waiting Room, MEXC Solana)
        if "пространство-время" in t_low or "эйнштейн" in t_low:
            return (
                "Предполагается, что высокоточные спутниковые и астрофизические измерения вращения массивных тел полностью подтверждают "
                "релятивистский эффект увлечения пространства-времени (эффект Лензе — Тирринга), предсказанный общей теорией относительности."
            )
        if "chatgpt" in t_low and ("strategy" in t_low or "сэйлор" in t_low or "saylor" in t_low):
            return (
                "Предполагается, что применение ИИ-моделей в корпоративном казначействе и финансовом структурировании позволяет компаниям "
                "масштабировать выпуск долговых и долевых инструментов (на десятки миллиардов долларов) для накопления резервов в Bitcoin."
            )
        if ("фонд ethereum" in t_low or "ethereum foundation" in t_low) and "бюджет" in t_low:
            return (
                "Предполагается проведение масштабной реструктуризации Ethereum Foundation с сокращением операционных расходов на 40% "
                "и перераспределением ресурсов в пользу базовой разработки протокола L1, масштабирования и криптографических исследований."
            )
        if "комнате ожидания" in t_low or ("альткоин" in t_low and "рывк" in t_low) or "альтсезон" in t_low:
            base = (
                "Предполагается, что после фазы консолидации и снижения доминации Bitcoin начнется ротация ликвидности в сектор альткоинов, "
                "способная вызвать опережающий импульсный рост альтернативных блокчейн-экосистем."
            )
            return f"{base} {thesis}" if thesis else base
        if "post-quantum" in t_low or "quantum resistance" in t_low or "квантов" in t_low:
            return (
                "Предполагается успешное внедрение алгоритмов постквантовой криптографии в основной сети блокчейна (mainnet) "
                "для долгосрочной защиты пользовательских кошельков, узлов и смарт-контрактов от угроз квантовых вычислений."
            )
        if "mexc" in t_low and "solana" in t_low:
            return (
                "Предполагается укрепление рыночных позиций и курса Solana за счет высокой ончейн-активности в секторе DeFi, "
                "роста объемов на децентрализованных биржах и притока розничной ликвидности."
            )

        # 4. If the event has a substantive expert thesis quote attached, synthesize hypothesis + thesis
        if thesis:
            if dom == "crypto":
                if any(w in t_low for w in ["etf", "sec", "институционал", "казначейств", "суверенн", "резерв", "закон", "конгресс"]):
                    prefix = "Предполагается расширение институционального и регуляторного принятия цифровых активов с прямым притоком капитала в сектор."
                elif any(w in t_low for w in ["dex", "tvl", "defi", "l2", "zk", "tps", "firedancer", "стейблкоин", "usdt", "rwa", "токен"]):
                    prefix = "Предполагается структурный рост ончейн-метрик, пропускной способности и капитализации инфраструктурных блокчейн-протоколов."
                else:
                    prefix = "Предполагается реализация бычьего ончейн-сценария и переоценка рыночной стоимости актива в текущем цикле."
            elif dom == "macro":
                if any(w in t_low for w in ["ставк", "фрс", "ецб", "дкп", "цб", "баланс"]):
                    prefix = "Предполагается сдвиг в денежно-кредитной политике центробанков под влиянием динамики инфляции, рынка труда и долговой нагрузки."
                elif any(w in t_low for w in ["s&p", "nasdaq", "акци", "индекс", "офз"]):
                    prefix = "Предполагается направленная переоценка фондового и долгового рынка на фоне изменения корпоративной рентабельности и макроусловий."
                else:
                    prefix = "Предполагается усиление макроэкономического тренда на защитные активы, сырьевые рынки и альтернативные валютные расчеты."
            elif dom == "tech":
                if any(w in t_low for w in ["агент", "saas", "код", "штат", "автоматизац"]):
                    prefix = "Предполагается качественный скачок в автоматизации разработки ПО и бизнес-процессов за счет внедрения автономных ИИ-агентов."
                elif any(w in t_low for w in ["аэс", "capex", "дата-центр", "чип", "инфраструктур"]):
                    prefix = "Предполагается масштабное наращивание инвестиций тех-гигантов в вычислительные мощности и энергетическую базу для ИИ."
                else:
                    prefix = "Предполагается технологический прорыв в возможностях моделей искусственного интеллекта и их промышленном применении."
            else:
                prefix = "Предполагается реализация заявленного сценария при подтверждении ключевых отраслевых и рыночных индикаторов."
            return f"{prefix} Обоснование: {thesis}"

        # 5. Clean semantic fallback by topic keywords (for NarrativeClusters and new events without statements yet)
        if dom == "crypto":
            if any(w in t_low for w in ["etf", "sec", "резерв", "закон", "конгресс", "nasdaq-100"]):
                return (
                    "Предполагается принятие официального регуляторного или корпоративного решения по включению криптоактивов "
                    "в биржевые фонды (ETF), государственные резервы или балансы публичных компаний."
                )
            if any(w in t_low for w in ["dex", "tvl", "defi", "l2", "base", "solana", "tps", "ton"]):
                return (
                    "Предполагается опережающий рост пользовательской активности, объемов торгов на DEX или заблокированной ликвидности (TVL) "
                    "в рассматриваемой блокчейн-экосистеме относительно конкурентов."
                )
            if any(w in t_low for w in ["стейблкоин", "usdt", "usdc", "rwa", "облигац"]):
                return (
                    "Предполагается расширение капитализации стейблкоинов и токенизированных реальных активов (RWA) на блокчейне "
                    "за счет спроса на трансграничные расчеты и казначейскую доходность."
                )
            return (
                "Предполагается изменение рыночной капитализации и ценового тренда цифрового актива под влиянием притока ликвидности, "
                "ончейн-спроса и макроэкономического цикла."
            )
        if dom == "macro":
            if any(w in t_low for w in ["ставк", "фрс", "ецб", "инфляц", "cpi"]):
                return (
                    "Предполагается достижение целевых макроэкономических показателей по инфляции и процентным ставкам центробанков "
                    "в соответствии с публикуемой официальной статистикой."
                )
            if any(w in t_low for w in ["госдолг", "долг", "dxy", "доллар", "золот"]):
                return (
                    "Предполагается рост долговой нагрузки и ослабление покупательной способности фиатных валют, "
                    "стимулирующее переток капитала в золото и защитные активы."
                )
            return (
                "Предполагается реализация макроэкономического сценария в динамике фондовых индексов, долговых рынков и мировой торговли."
            )
        if dom == "tech":
            return (
                "Предполагается достижение технологического рубежа в развитии ИИ-моделей, автономной робототехники и вычислительной инфраструктуры "
                "с подтверждением в отраслевых бенчмарках и корпоративных отчетах."
            )
        return (
            "Предполагается наступление указанного события при выполнении проверяемых фактических условий и подтверждении в официальных источниках."
        )

    @classmethod
    def generate_ai_topic_analysis(
        cls,
        title: str,
        domain: Optional[str] = None,
        probability: float = 0.5,
        statements_count: int = 0,
        keywords: Optional[List[str]] = None,
        statements: Optional[List[Any]] = None
    ) -> Dict[str, Any]:
        """
        Generates a structured hypothesis description and evaluation factors
        for a selected topic, narrative cluster, or forecasting event.
        """
        t_clean = cls.clean_event_title(title)
        t_low = t_clean.lower()
        dom = (domain or cls.infer_domain(t_clean)).lower()
        prob_pct = round(probability * 100)

        context = cls.build_hypothesis_description(t_clean, dom, statements=statements)

        # Domain-specific drivers and risk factors
        if dom == "crypto":
            if any(w in t_low for w in ["bitcoin", "биткоин", "биткойн", "btc", "резерв"]):
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
                oracle_criteria = "Автоматическая сверка спотовой котировки BTC/USDT и ранга капитализации через API бирж (Binance / CoinGecko / CompaniesMarketCap)."
            elif any(w in t_low for w in ["solana", "солана", "sol", "dex"]):
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
                bull_factors = [
                    "Рост совокупной капитализации крипторынка и приток свежей ликвидности",
                    "Поддержка тренда со стороны профильных аналитиков с высоким рейтингом доверия"
                ]
                bear_factors = [
                    "Высокая волатильность криптоактивов и зависимость от склонности к риску (Risk-On/Risk-Off)",
                    "Риск коррекции после локального перегрева рынка"
                ]
                oracle_criteria = "Проверка котировок и ончейн-фактов через автоматический крипто-оракул TruthOdds."

        elif dom == "macro":
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
            bull_factors = [
                "Наличие верифицируемых эмпирических данных и независимых подтверждений в источниках",
                "Соответствие наблюдаемым отраслевым и научным трендам"
            ]
            bear_factors = [
                "Неопределенность внешних факторов и сроков официальной верификации",
                "Наличие альтернативных интерпретаций или задержек в публикации данных"
            ]
            oracle_criteria = "Подтверждение факта по официальным отчетам, рецензируемым публикациям и верифицированным источникам данных."

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


