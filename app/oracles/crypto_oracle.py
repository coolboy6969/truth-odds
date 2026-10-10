import re
from typing import Dict, Any, Optional, List
import httpx
from sqlalchemy.orm import Session
from app.models.entities import Event
from app.engine.resolution import ResolutionEngine

class CryptoPriceOracle:
    """
    Automated Oracle that fetches live crypto prices and checks/resolves price-target events.
    """

    COINGECKO_URL = "https://api.coingecko.com/api/v3/simple/price"

    @classmethod
    async def get_live_prices(cls) -> Dict[str, float]:
        """
        Fetches live USD spot prices for major cryptocurrencies.
        """
        params = {
            "ids": "bitcoin,ethereum,solana,binancecoin,ripple",
            "vs_currencies": "usd",
            "include_24hr_change": "true"
        }
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.get(cls.COINGECKO_URL, params=params)
                resp.raise_for_status()
                data = resp.json()
                return {
                    "BTC": float(data.get("bitcoin", {}).get("usd", 0)),
                    "ETH": float(data.get("ethereum", {}).get("usd", 0)),
                    "SOL": float(data.get("solana", {}).get("usd", 0)),
                    "BNB": float(data.get("binancecoin", {}).get("usd", 0)),
                    "XRP": float(data.get("ripple", {}).get("usd", 0)),
                }
        except Exception as e:
            # Fallback mock/cache values if rate limited
            return {
                "BTC": 97500.0,
                "ETH": 3450.0,
                "SOL": 210.0,
                "BNB": 650.0,
                "XRP": 1.85,
                "note": f"Fallback/cached prices used ({e})"
            }

    # Actual global market-cap rankings (among all world assets: Gold, Apple, NVIDIA, Microsoft, etc.)
    # and crypto-only market-cap rankings for 2024–2026 verification
    ASSET_RANKINGS = {
        "BTC": {"global_rank": 8, "crypto_rank": 1, "mcap_label": "~$1.8 трлн"},
        "ETH": {"global_rank": 28, "crypto_rank": 2, "mcap_label": "~$380 млрд"},
        "XRP": {"global_rank": 190, "crypto_rank": 4, "mcap_label": "~$110 млрд"},
        "SOL": {"global_rank": 160, "crypto_rank": 5, "mcap_label": "~$95 млрд"},
        "BNB": {"global_rank": 210, "crypto_rank": 6, "mcap_label": "~$90 млрд"},
    }

    MIN_VALID_UNIT_PRICE = {
        "BTC": 5000.0,
        "ETH": 200.0,
        "SOL": 5.0,
        "BNB": 20.0,
        "XRP": 0.05,
    }

    MAX_VALID_UNIT_PRICE = {
        "BTC": 10000000.0,
        "ETH": 500000.0,
        "SOL": 50000.0,
        "BNB": 100000.0,
        "XRP": 1000.0,
    }

    @classmethod
    def detect_asset(cls, title: str) -> Optional[str]:
        title_lower = (title or "").lower()
        if any(k in title_lower for k in ["bitcoin", "биткоин", "биткойн", "btc"]):
            return "BTC"
        elif any(k in title_lower for k in ["ethereum", "эфириум", "эфир", "eth"]):
            return "ETH"
        elif any(k in title_lower for k in ["solana", "солана", "sol"]):
            return "SOL"
        elif any(k in title_lower for k in ["binance", "bnb"]):
            return "BNB"
        elif any(k in title_lower for k in ["ripple", "xrp"]):
            return "XRP"
        return None

    @classmethod
    def is_negated_claim(cls, title: str) -> bool:
        title_lower = (title or "").lower()
        return bool(
            re.search(
                r'\bне\s+(?:войдет|станет|попадет|будет|окажется|удержится|сможет|входит|достигнет|превысит|пробьет|вырастет|поднимется|упадет|опустится)\b',
                title_lower,
            )
            or re.search(r'\b(?:вылетит|выбывает|покинет)\s+из\s+топ', title_lower)
        )

    @classmethod
    def parse_event_ranking_claim(cls, title: str) -> Optional[Dict[str, Any]]:
        """
        Detects claims about an asset entering or not entering the Top-N assets or cryptocurrencies,
        e.g. 'биткоин не войдет в топ 10 активов 2025 года' or 'БИткоин станет топ 100 активом 2025 года'.
        """
        title_lower = (title or "").lower()
        asset = cls.detect_asset(title_lower)
        if not asset or asset not in cls.ASSET_RANKINGS:
            return None

        match_top = re.search(r'\b(?:топ|top)[-\s]*(\d{1,4})\b', title_lower)
        if not match_top:
            return None

        top_n = int(match_top.group(1))
        if top_n <= 0:
            return None

        is_crypto_only = any(w in title_lower for w in ["криптовалют", "криптоактив", "монет", "альткоин", "токенов"])
        rank_info = cls.ASSET_RANKINGS[asset]
        actual_rank = rank_info["crypto_rank"] if is_crypto_only else rank_info["global_rank"]
        scope_label = "криптоактивов" if is_crypto_only else "крупнейших мировых активов"

        is_negated = cls.is_negated_claim(title_lower)

        target_year = None
        match_year = re.search(r'\b(20[123][0-9])\b', title_lower)
        if match_year:
            target_year = int(match_year.group(1))

        in_top_n = actual_rank <= top_n
        # If negated ('не войдет в топ 10'), the statement is True only if the asset is NOT in top_n
        statement_is_true = (not in_top_n) if is_negated else in_top_n

        return {
            "asset": asset,
            "top_n": top_n,
            "actual_rank": actual_rank,
            "mcap_label": rank_info["mcap_label"],
            "scope_label": scope_label,
            "is_negated": is_negated,
            "in_top_n": in_top_n,
            "statement_is_true": statement_is_true,
            "target_year": target_year,
        }

    @classmethod
    def parse_event_price_target(cls, title: str) -> Optional[Dict[str, Any]]:
        """
        Detects asset and unit dollar price target from title.
        Strictly ignores years (e.g. 2025, 2026), rankings (топ 10), TPS (100,000 TPS),
        percentages, and macro/market-cap values in millions/billions/trillions ($100 млрд).
        """
        title_lower = (title or "").lower()
        asset = cls.detect_asset(title_lower)
        if not asset:
            return None

        # 1. Exclude ranking claims, TPS claims, dominance, and ratios
        if cls.parse_event_ranking_claim(title_lower):
            return None
        if any(w in title_lower for w in ["tps", "транзакц", "доминац", "eth/btc", "mvrv"]):
            return None

        # 2. Extract target year before stripping years from text
        target_year = None
        match_year = re.search(r'\b(20[123][0-9])\b', title_lower)
        if match_year:
            target_year = int(match_year.group(1))

        # 3. Strip years, rankings, and numbers with non-unit-price suffixes (млрд, трлн, млн, %, tps, etc.)
        cleaned = re.sub(
            r'\b(?:в|к|до|за|по итогам|конца|началу|после)?\s*20[123][0-9]\s*(?:год[ауеом]*|г\.)?\b',
            ' ',
            title_lower,
        )
        cleaned = re.sub(r'\b(?:топ|top)[-\s]*\d+\b', ' ', cleaned)
        cleaned = re.sub(
            r'\$?\d+(?:[.,\s]\d+)*\s*(?:млрд|трлн|млн|billion|trillion|million|bn|tn|tps|%|процент\w*|актив\w*|мест\w*|кошельк\w*|адрес\w*|компани\w*|человек\w*|раз\w*|пункт\w*|лет|год\w*|дн\w*|мес\w*)\b',
            ' ',
            cleaned,
        )

        # 4. Detect direction & negation
        is_downward = any(
            w in title_lower
            for w in ["упадет", "рухнет", "опустится", "падение ниже", "снизится ниже", "fall below", "drop below", "crash"]
        )
        is_negated = cls.is_negated_claim(title_lower)

        # 5. Extract unit price target only when accompanied by explicit currency/price markers
        target = None

        # 5a. $150k / 150k USD / $150 тыс
        match_k = re.search(
            r'(?:\$\s*(\d+(?:\.\d+)?)\s*(?:k|к|тыс\w*)|(\d+(?:\.\d+)?)\s*(?:k|к|тыс\w*)\s*(?:\$|usd|usdt|доллар\w*))',
            cleaned,
        )
        if match_k:
            num_str = match_k.group(1) or match_k.group(2)
            target = float(num_str) * 1000.0
        else:
            # 5b. Explicit $ or USD/доллар with thousands separator ($150,000 or $200 000)
            match_curr_sep = re.search(
                r'(?:\$\s*(\d{1,3}(?:[,\s]\d{3})+)|(\d{1,3}(?:[,\s]\d{3})+)\s*(?:\$|usd|usdt|доллар\w*))',
                cleaned,
            )
            if match_curr_sep:
                raw_num = (match_curr_sep.group(1) or match_curr_sep.group(2)).replace(",", "").replace(" ", "")
                target = float(raw_num)
            else:
                # 5c. Explicit $ or USD/доллар with plain digits ($3000, $150000)
                match_curr_plain = re.search(
                    r'(?:\$\s*(\d{2,7}(?:\.\d+)?)|(\d{2,7}(?:\.\d+)?)\s*(?:\$|usd|usdt|доллар\w*))',
                    cleaned,
                )
                if match_curr_plain:
                    raw_num = match_curr_plain.group(1) or match_curr_plain.group(2)
                    target = float(raw_num)
                elif any(p in title_lower for p in ["цена", "курс", "котировк", "отметк", "уровен"]):
                    # 5d. Explicit price word + comma-formatted number (e.g. "достигнет отметки 150,000")
                    match_price_sep = re.search(r'\b(\d{1,3}(?:,\d{3})+)\b', cleaned)
                    if match_price_sep:
                        target = float(match_price_sep.group(1).replace(",", ""))

        if target is None:
            return None

        # 6. Validate against realistic unit price bounds for the asset
        min_p = cls.MIN_VALID_UNIT_PRICE.get(asset, 0.01)
        max_p = cls.MAX_VALID_UNIT_PRICE.get(asset, 10000000.0)
        if target < min_p or target > max_p:
            return None

        return {
            "asset": asset,
            "target": target,
            "direction": "down" if is_downward else "up",
            "is_negated": is_negated,
            "target_year": target_year,
        }

    @classmethod
    async def evaluate_active_crypto_events(cls, db: Session, auto_resolve: bool = False) -> List[Dict[str, Any]]:
        """
        Compares all active crypto events against current prices.
        If auto_resolve is True and target reached, resolves event accordingly.
        """
        prices = await cls.get_live_prices()
        active_events = db.query(Event).filter(Event.status == "ACTIVE", Event.domain == "crypto").all()
        results = []

        for ev in active_events:
            target_info = cls.parse_event_price_target(ev.title)
            if not target_info:
                continue

            asset = target_info["asset"]
            target_price = target_info["target"]
            direction = target_info.get("direction", "up")
            is_negated = target_info.get("is_negated", False)
            current_price = prices.get(asset, 0)
            target_reached = (current_price >= target_price) if direction == "up" else (current_price <= target_price)

            item = {
                "event_id": ev.id,
                "event_title": ev.title,
                "asset": asset,
                "current_price": current_price,
                "target_price": target_price,
                "target_reached": target_reached,
                "progress_pct": round((current_price / target_price) * 100, 1) if target_price > 0 else 0,
                "status": ev.status
            }

            if target_reached and auto_resolve:
                outcome = False if is_negated else True
                ResolutionEngine.resolve_event(
                    db=db,
                    event_id=ev.id,
                    outcome=outcome,
                    resolution_notes=(
                        f"Автоматически опровергнуто оракулом: цена {asset} (${current_price:,.2f}) преодолела ${target_price:,.2f}"
                        if is_negated
                        else f"Автоматически подтверждено оракулом: цена {asset} (${current_price:,.2f}) достигла целевой отметки ${target_price:,.2f}"
                    ),
                )
                item["status"] = "RESOLVED_TRUE" if outcome else "RESOLVED_FALSE"
                item["resolved"] = True

            results.append(item)

        return results
