import re
from typing import List, Dict, Any, Optional
from sqlalchemy.orm import Session
from app.models.entities import DiscoveredSpeakerCandidate, Speaker
from app.services.prediction_service import PredictionService

import urllib.parse

SINGLE_WORD_ALLOWLIST = {"planb", "satoshi", "cobie"}
KNOWN_ANALYSTS_ALLOWLIST = {
    "planb", "satoshi", "cobie", "satoshi nakamoto",
    "guy turner", "guy turner (coin bureau)",
    "altcoin daily", "altcoin daily (aaron & austin)"
}

STOP_WORDS = {
    # Time and calendar words (RU & EN)
    "год", "года", "году", "годом", "годах", "лет", "месяц", "месяца", "месяцы", "день", "дня", "дни",
    "неделя", "недели", "сегодня", "завтра", "вчера", "цикл", "халвинг", "срок", "время", "времена",
    "сезон", "ралли", "дата", "час", "часы", "минуты", "квартал",
    "time", "year", "years", "month", "months", "day", "days", "week", "weeks", "hour", "hours",
    "today", "tomorrow", "yesterday", "cycle", "halving", "period", "era", "date", "hourly",
    "daily", "weekly", "monthly", "quarter",

    # Actions, verbs and participles (RU & EN)
    "купить", "продать", "держит", "держится", "предсказывает", "предсказал", "спрогнозировал",
    "заявил", "заявила", "предупредил", "предупреждает", "призвал", "призвала", "считает",
    "ожидается", "ожидает", "видит", "назвал", "назвала", "советует", "ждет", "ждать", "пробил",
    "пробивает", "обвалился", "обвалится", "растет", "вырастет", "падает", "упадет", "рухнет",
    "торгуется", "взлетел", "достиг", "достигнет", "отметил", "отметила", "уверен", "уверена",
    "buy", "sell", "hold", "predicts", "predicted", "prediction", "predictions", "forecasts",
    "forecasted", "says", "said", "warns", "warned", "praises", "bets", "apologizes", "sees",
    "expects", "calls", "called", "targets", "notes", "noted", "believes", "believed", "argues",
    "claims", "claimed", "surges", "drops", "crashes", "moons", "dumps", "pumps", "rallies",
    "breaks", "broken", "reaches", "hit", "hits", "trades", "trading", "drops truth",

    # Crypto & Financial tokens and market terms (RU & EN)
    "bitcoin", "биткоин", "crypto", "крипта", "ethereum", "эфириум", "solana", "солана",
    "xrp", "рипл", "btc", "eth", "sol", "doge", "cardano", "ada", "binance", "coinbase",
    "altcoin", "альткоин", "альткоины", "token", "токен", "токены", "coin", "монета", "монеты",
    "рынок", "рынка", "рынки", "маркет", "биржа", "биржи", "market", "markets", "price", "prices",
    "цена", "цены", "цену", "курс", "курса", "курсы", "target", "targets", "таргет", "таргеты",
    "цель", "цели", "пробой", "отскок", "уровень", "уровни", "поддержка", "сопротивление",
    "wall", "street", "фрс", "fed", "sec", "recession", "рецессия", "inflation", "инфляция",
    "bull", "bear", "бык", "медведь", "бычий", "бычьи", "медвежий", "медвежьи", "etf", "фонд",
    "dex", "cex", "dao", "defi", "reserve", "резерв", "dollar", "доллар", "рубль", "ruble",
    "золото", "gold", "нефть", "oil", "s&p", "nasdaq", "dow", "index", "индекс",
    "standard", "chartered", "bloomberg", "reuters", "coindesk", "cointelegraph", "cnbc",
    "forbes", "yahoo", "finance", "cryptorank", "beincrypto", "traders", "union", "cryptonews",
    "ripple", "bitcoiners", "kucoin", "bitget", "bybit", "kraken",

    # Professions and media titles (RU & EN)
    "analyst", "analysts", "аналитик", "аналитики", "expert", "experts", "эксперт", "эксперты",
    "economist", "economists", "экономист", "экономисты", "trader", "traders", "трейдер", "трейдеры",
    "investor", "investors", "инвестор", "инвесторы", "author", "authors", "автор", "авторы",
    "journalist", "journalists", "журналист", "журналисты", "ceo", "cto", "founder", "founders",
    "основатель", "глава", "руководитель", "президент", "director", "directors", "директор",
    "новости", "news", "report", "reports", "отчет", "обзор", "обзоры", "interview", "интервью",
    "review", "podcast", "подкаст", "video", "видео", "сми", "канал", "медиа",

    # Adjectives, superlatives & descriptors (RU & EN)
    "самый", "самая", "самое", "самые", "влиятельный", "влиятельные", "лучший", "лучшие",
    "главный", "главные", "новый", "новая", "новые", "крупный", "крупные", "исторический",
    "рекордный", "невероятный", "возможный", "следующий", "последний", "первый",
    "top", "best", "worst", "big", "bigger", "biggest", "major", "new", "latest", "next",
    "first", "last", "historic", "record", "incredible", "real", "possible", "likely", "unlikely",
    "potential", "true", "false", "great", "greatest",

    # Prepositions, conjunctions, pronouns (RU & EN)
    "who", "кто", "which", "который", "that", "что", "for", "для", "with", "с", "on", "на",
    "in", "в", "from", "из", "от", "to", "к", "до", "по", "and", "и", "or", "или", "as", "как",
    "at", "by", "about", "о", "об", "previously", "again", "already", "soon", "still", "just",
    "now", "ранее", "снова", "уже", "скоро", "почему", "зачем", "где", "когда"
}

def normalize_analyst_url(url: Optional[str]) -> str:
    """
    Normalizes article or source URLs by stripping tracking parameters,
    trailing slashes, and protocols to identify identical references.
    """
    if not url:
        return ""
    clean = url.strip()
    try:
        parsed = urllib.parse.urlparse(clean)
        # Strip tracking query params
        if parsed.query:
            pairs = urllib.parse.parse_qsl(parsed.query)
            filtered = [(k, v) for k, v in pairs if not k.startswith("utm_") and k not in ("oc", "ref", "source", "fbclid")]
            query_str = urllib.parse.urlencode(filtered)
        else:
            query_str = ""
        normalized = urllib.parse.urlunparse((
            parsed.scheme.lower(),
            parsed.netloc.lower(),
            parsed.path.rstrip('/'),
            "",
            query_str,
            ""
        ))
        return normalized
    except Exception:
        return clean.rstrip('/')

def is_valid_analyst_name(name: Optional[str]) -> bool:
    """
    Strict validation for analyst human names. Rejects random words, market slang,
    time tokens (like 'Год'), verbs, headlines, or single non-allowlisted words.
    """
    if not name:
        return False
    name_clean = name.strip()
    if len(name_clean) < 3 or len(name_clean) > 45:
        return False

    name_lower = name_clean.lower()
    if name_lower in KNOWN_ANALYSTS_ALLOWLIST:
        return True

    # Reject names containing digits
    if any(char.isdigit() for char in name_clean):
        return False

    # Reject names containing headline punctuation or symbols
    if any(char in name_clean for char in (':', ';', '?', '!', '"', '«', '»', '/', '\\', '%', '$', '€', '£', '@', '#', '*')):
        return False

    words = name_clean.split()
    if len(words) not in (2, 3):
        return False

    for w in words:
        w_clean = re.sub(r'^[^\w]+|[^\w]+$', '', w.lower())
        if not w_clean or len(w_clean) < 2:
            return False
        if w_clean in STOP_WORDS:
            return False
        if not w[0].isupper():
            return False
        # Ensure word is comprised strictly of alphabetic characters (unicode letters) or hyphen/apostrophe
        w_letters = re.sub(r"[\-\']", "", w)
        if not w_letters.isalpha():
            return False

    return True


KNOWN_RU_EN_FULL_NAMES = {
    "роберт кийосаки": "Robert Kiyosaki",
    "евгений коган": "Evgeny Kogan",
    "александр герчик": "Alexander Gerchik",
    "рафаэль манвелян": "Rafael Manvelyan",
    "василий олейник": "Vasily Oleynik",
    "кирилл эванс": "Kirill Evans",
    "анатолий радченко": "Anatoly Radchenko",
    "михаил хазин": "Mikhail Khazin",
    "евгений надоршин": "Evgeny Nadorshin",
    "александр лосев": "Alexander Losev",
    "ярослав кабаков": "Yaroslav Kabakov",
    "дмитрий солодин": "Dmitry Solodin",
    "тимофей мартынов": "Timofey Martynov",
    "артур хейс": "Arthur Hayes",
    "майкл сэйлор": "Michael Saylor",
    "майкл сейлор": "Michael Saylor",
    "виталик бутерин": "Vitalik Buterin",
    "кэти вуд": "Cathie Wood",
    "питер шифф": "Peter Schiff",
    "рауль пал": "Raoul Pal",
    "питер брандт": "Peter Brandt",
    "том ли": "Tom Lee",
    "бенджамин коуэн": "Benjamin Cowen",
    "вилли ву": "Willy Woo",
    "лин олден": "Lyn Alden",
    "дэн тапиеро": "Dan Tapiero",
    "илон маск": "Elon Musk",
    "сэм альтман": "Sam Altman",
    "павел дуров": "Pavel Durov",
    "билл акман": "Bill Ackman",
    "рэй далио": "Ray Dalio",
    "уоррен баффет": "Warren Buffett",
    "джером пауэлл": "Jerome Powell",
    "ларри финк": "Larry Fink",
    "чарльз хоскинсон": "Charles Hoskinson",
    "анатолий яковенко": "Anatoly Yakovenko",
    "брайан армстронг": "Brian Armstrong",
    "майк новограц": "Mike Novogratz",
    "энтони помплиано": "Anthony Pompliano",
    "альберт эйнштейн": "Albert Einstein",
    "albert eynshteyn": "Albert Einstein",
    "дональд трамп": "Donald Trump",
    "уоррен баффетт": "Warren Buffett",
    "джастин сан": "Justin Sun",
    "ричард тенг": "Richard Teng",
}

KNOWN_RU_EN_WORDS = {
    "александр": "Alexander", "александра": "Alexander", "александром": "Alexander",
    "евгений": "Evgeny", "евгения": "Evgeny", "евгением": "Evgeny",
    "дмитрий": "Dmitry", "дмитрия": "Dmitry", "дмитрием": "Dmitry",
    "василий": "Vasily", "василия": "Vasily", "василием": "Vasily",
    "анатолий": "Anatoly", "анатолия": "Anatoly", "анатолием": "Anatoly",
    "рафаэль": "Rafael", "рафаэля": "Rafael",
    "кирилл": "Kirill", "кирилла": "Kirill",
    "михаил": "Mikhail", "михаила": "Mikhail",
    "ярослав": "Yaroslav", "ярослава": "Yaroslav",
    "тимофей": "Timofey", "тимофея": "Timofey",
    "алексей": "Alexey", "алексея": "Alexey",
    "сергей": "Sergey", "сергея": "Sergey",
    "андрей": "Andrey", "андрея": "Andrey",
    "николай": "Nikolay", "николая": "Nikolay",
    "юрий": "Yury", "юрия": "Yury",
    "валерий": "Valery", "валерия": "Valery",
    "виталий": "Vitaly", "виталия": "Vitaly",
    "григорий": "Grigory", "григория": "Grigory",
    "георгий": "Georgy", "георгия": "Georgy",
    "максим": "Maxim", "максима": "Maxim",
    "виктор": "Victor", "виктора": "Victor",
    "павел": "Pavel", "павла": "Pavel",
    "илья": "Ilya", "ильи": "Ilya",
    "пётр": "Peter", "петр": "Peter", "петра": "Peter",
    "фёдор": "Fedor", "федор": "Fedor", "федора": "Fedor",
    "роберт": "Robert", "роберта": "Robert",
    "майкл": "Michael", "майкла": "Michael",
    "питер": "Peter", "питера": "Peter",
    "артур": "Arthur", "артура": "Arthur",
    "альберт": "Albert", "альберта": "Albert",
    "эйнштейн": "Einstein", "эйнштейна": "Einstein",
    "илон": "Elon", "илона": "Elon",
    "сэм": "Sam", "сэма": "Sam",
    "кэти": "Cathie",
    "эванс": "Evans",
    "кийосаки": "Kiyosaki",
    "коган": "Kogan", "когана": "Kogan",
    "герчик": "Gerchik", "герчика": "Gerchik",
    "манвелян": "Manvelyan", "манвеляна": "Manvelyan",
    "олейник": "Oleynik", "олейника": "Oleynik",
    "радченко": "Radchenko",
    "хазин": "Khazin", "хазина": "Khazin",
    "надоршин": "Nadorshin", "надоршина": "Nadorshin",
    "лосев": "Losev", "лосева": "Losev",
    "кабаков": "Kabakov", "кабакова": "Kabakov",
    "солодин": "Solodin", "солодина": "Solodin",
    "мартынов": "Martynov", "мартынова": "Martynov",
}

CYRILLIC_TO_LATIN_MAP = {
    'а': 'a', 'б': 'b', 'в': 'v', 'г': 'g', 'д': 'd', 'е': 'e', 'ё': 'yo',
    'ж': 'zh', 'з': 'z', 'и': 'i', 'й': 'y', 'к': 'k', 'л': 'l', 'м': 'm',
    'н': 'n', 'о': 'o', 'п': 'p', 'р': 'r', 'с': 's', 'т': 't', 'у': 'u',
    'ф': 'f', 'х': 'kh', 'ц': 'ts', 'ч': 'ch', 'ш': 'sh', 'щ': 'shch',
    'ъ': '', 'ы': 'y', 'ь': '', 'э': 'e', 'ю': 'yu', 'я': 'ya'
}


def transliterate_russian_name_to_english(name: Optional[str]) -> str:
    """
    Transcribes/transliterates any Russian (Cyrillic) candidate or analyst name into English.
    Uses canonical spelling for known personalities and natural English transliteration for new names.
    """
    if not name:
        return ""
    clean = " ".join(name.strip().split())
    low_full = clean.lower()
    if low_full in KNOWN_RU_EN_FULL_NAMES:
        return KNOWN_RU_EN_FULL_NAMES[low_full]

    if not re.search(r'[А-Яа-яЁё]', clean):
        return " ".join(w[0].upper() + w[1:] if w else w for w in clean.split())

    out_words = []
    for raw_w in clean.split():
        w_low = raw_w.lower()
        if w_low in KNOWN_RU_EN_WORDS:
            out_words.append(KNOWN_RU_EN_WORDS[w_low])
            continue
        if not re.search(r'[а-яё]', w_low):
            out_words.append(raw_w.capitalize())
            continue

        # Handle natural Russian name endings (-ий / -ый -> -y, -ей -> -ey, -ия -> -ia)
        suffix = ""
        stem = w_low
        if len(w_low) > 3 and (w_low.endswith("ий") or w_low.endswith("ый")):
            stem = w_low[:-2]
            suffix = "y"
        elif len(w_low) > 3 and w_low.endswith("ей"):
            stem = w_low[:-2]
            suffix = "ey"
        elif len(w_low) > 3 and w_low.endswith("ия"):
            stem = w_low[:-2]
            suffix = "ia"

        stem = stem.replace("кс", "x")
        trans_chars = [CYRILLIC_TO_LATIN_MAP.get(ch, ch) for ch in stem]
        latin_word = "".join(trans_chars) + suffix
        out_words.append(latin_word.capitalize() if latin_word else raw_w)

    result_name = " ".join(out_words)
    if result_name.lower() in KNOWN_RU_EN_FULL_NAMES:
        return KNOWN_RU_EN_FULL_NAMES[result_name.lower()]
    return result_name


class SpeakerDiscoveryEngine:
    """
    Discovers new opinion leaders and forecasting personalities by analyzing
    co-occurrence networks, guest mentions, and interviews across social channels.
    """

    GUEST_PATTERNS = [
        # English patterns
        r'(?:interview with|talking to|discussion with|featuring|guest:?)\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+){1,2})',
        r'([A-Z][a-z]+(?:\s+[A-Z][a-z]+){1,2})\s+(?:predicts|warns|explains|reveals|forecasts|drops truth)',
        r'(?:ft\.|feat\.|with)\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+){1,2})',
        # Russian patterns
        r'(?:интервью с|в гостях у нас|беседа с|прогноз от)\s+([А-ЯЁ][а-яё]+(?:\s+[А-ЯЁ][а-яё]+){1,2})',
        r'([А-ЯЁ][а-яё]+(?:\s+[А-ЯЁ][а-яё]+){1,2})\s+(?:прогнозирует|предупреждает|объясняет|дал прогноз)'
    ]

    @classmethod
    def extract_potential_speakers(cls, text_or_title: str) -> List[str]:
        found_names = set()
        for pattern in cls.GUEST_PATTERNS:
            matches = re.finditer(pattern, text_or_title, re.IGNORECASE)
            for m in matches:
                name = m.group(1).strip()
                name_cleaned = re.sub(r'\s+(?:on|in|for|who|at|by|says|predicts|на|в|для|кто|заявил)$', '', name, flags=re.IGNORECASE).strip()
                if is_valid_analyst_name(name_cleaned):
                    formatted_name = transliterate_russian_name_to_english(name_cleaned)
                    found_names.add(formatted_name)
        return list(found_names)

    @classmethod
    def register_or_update_candidate(
        cls,
        db: Session,
        name: str,
        channel_title: str,
        context_quote: str = "",
        contains_claim: bool = True,
        source_url: str = ""
    ) -> Optional[DiscoveredSpeakerCandidate]:
        if not is_valid_analyst_name(name):
            return None

        name_clean = transliterate_russian_name_to_english(name)

        # Check existing candidate by name
        candidate = db.query(DiscoveredSpeakerCandidate).filter(
            DiscoveredSpeakerCandidate.name.ilike(name_clean)
        ).first()

        # Check existing candidate by source_url (if URLs match, it is the exact same analyst)
        if not candidate and source_url:
            norm_url = normalize_analyst_url(source_url)
            for c in db.query(DiscoveredSpeakerCandidate).all():
                if c.source_url and normalize_analyst_url(c.source_url) == norm_url:
                    candidate = c
                    break

        if not candidate:
            # Check if already a full speaker before creating a brand-new candidate
            existing_speaker = db.query(Speaker).filter(Speaker.name.ilike(name_clean)).first()
            if existing_speaker:
                return None

        if candidate:
            candidate.name = name_clean
            candidate.mention_count += 1
            if contains_claim:
                candidate.claim_density_score = min(1.0, candidate.claim_density_score + 0.15)
            if context_quote and (not candidate.context_quote or len(candidate.context_quote) < 30):
                candidate.context_quote = context_quote[:300]
            if source_url and not candidate.source_url:
                candidate.source_url = source_url
        else:
            candidate = DiscoveredSpeakerCandidate(
                name=name_clean,
                discovered_via_channel=channel_title,
                context_quote=context_quote[:300] if context_quote else f"Обнаружен в контенте канала {channel_title}",
                source_url=source_url or None,
                mention_count=1,
                claim_density_score=0.65 if contains_claim else 0.40,
                status="CANDIDATE"
            )
            db.add(candidate)

        # Check for auto-promotion threshold: mentioned on multiple channels with good claim density
        if candidate.mention_count >= 2 and candidate.claim_density_score >= 0.60 and candidate.status == "CANDIDATE":
            cls.promote_candidate_to_speaker(db, candidate.id)

        db.commit()
        db.refresh(candidate)
        return candidate

    @classmethod
    def promote_candidate_to_speaker(cls, db: Session, candidate_id: str) -> Optional[Speaker]:
        candidate = db.query(DiscoveredSpeakerCandidate).filter(
            DiscoveredSpeakerCandidate.id == candidate_id
        ).first()
        if not candidate:
            return None

        speaker = PredictionService.get_or_create_speaker(
            db=db,
            name=candidate.name,
            handle_or_channel=f"Discovered via {candidate.discovered_via_channel}"
        )
        speaker.bio = f"Обнаружен автоматически через анализ контента ({candidate.mention_count} упоминаний)"
        
        candidate.status = "APPROVED"
        db.commit()
        db.refresh(speaker)
        return speaker
