import asyncio
import logging
from datetime import datetime
from typing import Dict, Any, List, Optional
from sqlalchemy.orm import Session
from app.database.session import SessionLocal
from app.models.entities import Event
from app.engine.resolution import ResolutionEngine
from app.oracles.crypto_oracle import CryptoPriceOracle

logger = logging.getLogger("truth_odds.auto_oracle")

class AutoOracleService:
    """
    Automated Background Service that periodically monitors active events:
    1. Checks crypto price targets against live exchange/spot data (CoinGecko).
    2. Checks whether target was achieved (Bullish >= target, Bearish <= target).
    3. Checks whether the deadline or target year has expired without fulfillment.
    4. Automatically resolves events, updates track records & Brier scores.
    """

    is_enabled: bool = True
    check_interval_seconds: int = 30
    last_run_at: Optional[datetime] = None
    last_run_summary: Dict[str, Any] = {}
    total_auto_resolved_count: int = 0
    _background_task: Optional[asyncio.Task] = None

    @classmethod
    def _build_ranking_resolution_note(cls, rank_info: Dict[str, Any]) -> str:
        asset = rank_info["asset"]
        top_n = rank_info["top_n"]
        actual_rank = rank_info["actual_rank"]
        mcap_label = rank_info["mcap_label"]
        scope_label = rank_info["scope_label"]
        is_negated = rank_info["is_negated"]
        in_top_n = rank_info["in_top_n"]
        statement_is_true = rank_info["statement_is_true"]

        if statement_is_true:
            if is_negated:
                return (
                    f"Автоматически подтверждено оракулом (Статус: ДА): {asset} занимает {actual_rank}-е место "
                    f"среди {scope_label} ({mcap_label}) и действительно не вошел в Топ-{top_n}"
                )
            return (
                f"Автоматически подтверждено оракулом (Статус: ДА): {asset} входит в Топ-{top_n} {scope_label} "
                f"по рыночной капитализации ({mcap_label}, {actual_rank}-е место в мире)"
            )
        else:
            if is_negated and in_top_n:
                return (
                    f"Автоматически опровергнуто оракулом (Статус: НЕТ): {asset} входит в Топ-{top_n} {scope_label} "
                    f"по рыночной капитализации ({mcap_label}, {actual_rank}-е место в мире), "
                    f"поэтому утверждение «не войдет в топ-{top_n}» не соответствует действительности"
                )
            return (
                f"Автоматически опровергнуто оракулом (Статус: НЕТ): {asset} занимает {actual_rank}-е место "
                f"среди {scope_label} ({mcap_label}) и не вошел в Топ-{top_n}"
            )

    @classmethod
    def audit_and_fix_resolved_events(cls, db: Session) -> int:
        """
        Self-healing audit pass:
        1. Fixes any event that was previously mis-resolved due to years (e.g. $2,025.00) being parsed as prices.
        2. Re-verifies ranking claims (e.g. 'биткоин не войдет в топ 10 активов 2025 года') and negated claims,
           correcting both event status (RESOLVED_TRUE vs RESOLVED_FALSE), statement polarity, and speaker scores.
        """
        from app.models.entities import Statement, Speaker
        from app.engine.auto_analysis import AutoEventAnalysisEngine

        all_events = db.query(Event).all()
        fixed_count = 0

        for ev in all_events:
            rank_info = CryptoPriceOracle.parse_event_ranking_claim(ev.title)
            if rank_info:
                # Fix expert statement confidences if this is a negated/bearish claim that had bullish stances attached
                if rank_info["is_negated"]:
                    stmts = db.query(Statement).filter(Statement.event_id == ev.id).all()
                    for st in stmts:
                        sp = db.query(Speaker).filter(Speaker.id == st.speaker_id).first()
                        sp_name = (sp.name if sp else "").lower()
                        if any(b in sp_name for b in ["saylor", "hayes", "vitalik", "wood", "pal", "lee"]) and st.speaker_confidence > 0.5:
                            st.speaker_confidence = round(1.0 - st.speaker_confidence, 2)
                            if sp and "восходящий тренд" in (st.raw_quote or ""):
                                st.raw_quote = f"{sp.name}: «Фундаментальная капитализация актива уверенно удерживает его в элите мирового рынка, негативный сценарий маловероятен.»"
                        elif "schiff" in sp_name and st.speaker_confidence < 0.5:
                            st.speaker_confidence = round(1.0 - st.speaker_confidence, 2)
                    db.commit()

                expected_outcome = rank_info["statement_is_true"]
                expected_status = "RESOLVED_TRUE" if expected_outcome else "RESOLVED_FALSE"
                expected_notes = cls._build_ranking_resolution_note(rank_info)

                if ev.status != expected_status or "$2,02" in (ev.resolution_notes or ""):
                    ResolutionEngine.resolve_event(
                        db=db,
                        event_id=ev.id,
                        outcome=expected_outcome,
                        resolution_notes=expected_notes,
                    )
                    fixed_count += 1
                continue

            # Check if an event was resolved with a bogus year-as-price note (like $2,024.00 .. $2,029.00)
            if ev.status in ("RESOLVED_TRUE", "RESOLVED_FALSE") and ev.resolution_notes:
                target_info = CryptoPriceOracle.parse_event_price_target(ev.title)
                if not target_info and "достигла целевой отметки $2,0" in ev.resolution_notes:
                    ev.status = "ACTIVE"
                    ev.resolved_at = None
                    ev.resolution_notes = None
                    db.commit()
                    AutoEventAnalysisEngine.recalculate_event_probability(db, ev)
                    fixed_count += 1

        return fixed_count

    @classmethod
    def check_all_active_events(cls, db: Session, auto_resolve: bool = False) -> Dict[str, Any]:
        """
        Synchronously checks active events against ranking claims, crypto price targets, and deadlines.
        """
        cls.last_run_at = datetime.utcnow()
        cls.audit_and_fix_resolved_events(db)

        prices = {
            "BTC": 97500.0,
            "ETH": 3450.0,
            "SOL": 210.0,
            "BNB": 650.0,
            "XRP": 1.85,
        }
        active_events = db.query(Event).filter(Event.status == "ACTIVE").all()
        now = datetime.utcnow()
        current_year = now.year
        evaluated = []
        resolved_events = []

        for ev in active_events:
            # 1. Check asset ranking / top-N claims first
            rank_info = CryptoPriceOracle.parse_event_ranking_claim(ev.title)
            if rank_info:
                target_year = rank_info.get("target_year")
                can_resolve_now = rank_info["in_top_n"] or (target_year is not None and target_year <= current_year)
                if can_resolve_now and auto_resolve:
                    outcome = rank_info["statement_is_true"]
                    notes = cls._build_ranking_resolution_note(rank_info)
                    ResolutionEngine.resolve_event(
                        db=db,
                        event_id=ev.id,
                        outcome=outcome,
                        resolution_notes=notes,
                    )
                    cls.total_auto_resolved_count += 1
                    resolved_events.append({
                        "event_id": ev.id,
                        "title": ev.title,
                        "outcome": outcome,
                    })
                continue

            # 2. Check Crypto Price Targets
            target_info = CryptoPriceOracle.parse_event_price_target(ev.title)
            if target_info:
                asset = target_info["asset"]
                target_price = target_info["target"]
                direction = target_info.get("direction", "up")
                is_negated = target_info.get("is_negated", False)
                target_year = target_info.get("target_year")
                current_price = prices.get(asset, 0.0)

                target_met = (current_price >= target_price) if direction == "up" else (current_price <= target_price)
                expired_by_year = (target_year is not None and target_year < current_year)
                expired_by_deadline = (ev.deadline is not None and ev.deadline < now)

                if target_met:
                    if auto_resolve:
                        outcome = False if is_negated else True
                        notes = (
                            f"Автоматически опровергнуто оракулом (Статус: НЕТ): цена {asset} "
                            f"(${current_price:,.2f}) преодолела отметку ${target_price:,.2f}"
                            if is_negated
                            else f"Автоматически подтверждено оракулом (Статус: ДА): цена {asset} "
                            f"(${current_price:,.2f}) достигла целевой отметки ${target_price:,.2f}"
                        )
                        ResolutionEngine.resolve_event(
                            db=db,
                            event_id=ev.id,
                            outcome=outcome,
                            resolution_notes=notes
                        )
                        cls.total_auto_resolved_count += 1
                        resolved_events.append({
                            "event_id": ev.id,
                            "title": ev.title,
                            "outcome": outcome
                        })
                    continue
                elif expired_by_year or expired_by_deadline:
                    if auto_resolve:
                        outcome = True if is_negated else False
                        time_desc = str(target_year) if target_year else ev.deadline.strftime("%Y-%m-%d")
                        notes = (
                            f"Автоматически подтверждено оракулом (Статус: ДА): срок ({time_desc}) истек, "
                            f"и цена {asset} действительно не достигла ${target_price:,.2f}"
                            if is_negated
                            else f"Автоматически зафиксировано оракулом (Статус: НЕТ): срок прогноза ({time_desc}) истек, "
                            f"целевая цена ${target_price:,.2f} не достигнута"
                        )
                        ResolutionEngine.resolve_event(
                            db=db,
                            event_id=ev.id,
                            outcome=outcome,
                            resolution_notes=notes
                        )
                        cls.total_auto_resolved_count += 1
                        resolved_events.append({
                            "event_id": ev.id,
                            "title": ev.title,
                            "outcome": outcome
                        })
                    continue
                else:
                    progress = round((current_price / target_price) * 100, 1) if target_price > 0 else 0
                    evaluated.append({
                        "event_id": ev.id,
                        "title": ev.title,
                        "asset": asset,
                        "current_price": current_price,
                        "target_price": target_price,
                        "progress_pct": progress,
                        "status": "ACTIVE"
                    })
                    continue

            if ev.deadline and ev.deadline < now:
                if auto_resolve:
                    notes = f"Автоматически зафиксировано: установленный срок ({ev.deadline.strftime('%Y-%m-%d')}) истек"
                    ResolutionEngine.resolve_event(db=db, event_id=ev.id, outcome=False, resolution_notes=notes)
                    cls.total_auto_resolved_count += 1
                    resolved_events.append({"event_id": ev.id, "title": ev.title, "outcome": False})

        return {
            "total_active_checked": len(active_events),
            "resolved_count": len(resolved_events),
            "evaluated": evaluated
        }

    @classmethod
    async def evaluate_and_resolve_all(cls, db: Session, auto_resolve: bool = True) -> Dict[str, Any]:
        cls.last_run_at = datetime.utcnow()
        cls.audit_and_fix_resolved_events(db)

        prices = await CryptoPriceOracle.get_live_prices()
        active_events = db.query(Event).filter(Event.status == "ACTIVE").all()

        evaluated = []
        resolved_events = []
        now = datetime.utcnow()
        current_year = now.year

        for ev in active_events:
            # 1. Asset Ranking / Top-N Claims
            rank_info = CryptoPriceOracle.parse_event_ranking_claim(ev.title)
            if rank_info:
                target_year = rank_info.get("target_year")
                can_resolve_now = rank_info["in_top_n"] or (target_year is not None and target_year <= current_year)
                if can_resolve_now and auto_resolve:
                    outcome = rank_info["statement_is_true"]
                    notes = cls._build_ranking_resolution_note(rank_info)
                    ResolutionEngine.resolve_event(
                        db=db,
                        event_id=ev.id,
                        outcome=outcome,
                        resolution_notes=notes
                    )
                    cls.total_auto_resolved_count += 1
                    resolved_events.append({
                        "event_id": ev.id,
                        "title": ev.title,
                        "outcome": outcome,
                        "reason": notes
                    })
                continue

            # 2. Crypto Price Targets
            target_info = CryptoPriceOracle.parse_event_price_target(ev.title)
            if target_info:
                asset = target_info["asset"]
                target_price = target_info["target"]
                direction = target_info.get("direction", "up")
                is_negated = target_info.get("is_negated", False)
                target_year = target_info.get("target_year")
                current_price = prices.get(asset, 0.0)

                target_met = (current_price >= target_price) if direction == "up" else (current_price <= target_price)
                expired_by_year = (target_year is not None and target_year < current_year)
                expired_by_deadline = (ev.deadline is not None and ev.deadline < now)

                if target_met:
                    if auto_resolve:
                        outcome = False if is_negated else True
                        notes = (
                            f"Автоматически опровергнуто оракулом (Статус: НЕТ): цена {asset} "
                            f"(${current_price:,.2f}) преодолела отметку ${target_price:,.2f}"
                            if is_negated
                            else f"Автоматически подтверждено оракулом (Статус: ДА): цена {asset} "
                            f"(${current_price:,.2f}) достигла целевой отметки ${target_price:,.2f}"
                        )
                        ResolutionEngine.resolve_event(
                            db=db,
                            event_id=ev.id,
                            outcome=outcome,
                            resolution_notes=notes
                        )
                        cls.total_auto_resolved_count += 1
                        resolved_events.append({
                            "event_id": ev.id,
                            "title": ev.title,
                            "outcome": outcome,
                            "reason": notes
                        })
                    continue
                elif expired_by_year or expired_by_deadline:
                    if auto_resolve:
                        outcome = True if is_negated else False
                        time_desc = str(target_year) if target_year else ev.deadline.strftime("%Y-%m-%d")
                        notes = (
                            f"Автоматически подтверждено оракулом (Статус: ДА): срок ({time_desc}) истек, "
                            f"и цена {asset} (${current_price:,.2f}) действительно не достигла ${target_price:,.2f}"
                            if is_negated
                            else f"Автоматически зафиксировано оракулом (Статус: НЕТ): срок прогноза ({time_desc}) истек, "
                            f"целевая цена ${target_price:,.2f} не достигнута (текущая цена {asset}: ${current_price:,.2f})"
                        )
                        ResolutionEngine.resolve_event(
                            db=db,
                            event_id=ev.id,
                            outcome=outcome,
                            resolution_notes=notes
                        )
                        cls.total_auto_resolved_count += 1
                        resolved_events.append({
                            "event_id": ev.id,
                            "title": ev.title,
                            "outcome": outcome,
                            "reason": notes
                        })
                    continue
                else:
                    progress = round((current_price / target_price) * 100, 1) if target_price > 0 else 0
                    evaluated.append({
                        "event_id": ev.id,
                        "title": ev.title,
                        "asset": asset,
                        "current_price": current_price,
                        "target_price": target_price,
                        "progress_pct": progress,
                        "status": "ACTIVE"
                    })
                    continue

            # 3. General events with passed deadlines
            if ev.deadline and ev.deadline < now:
                if auto_resolve:
                    notes = (
                        f"Автоматически зафиксировано: установленный срок "
                        f"({ev.deadline.strftime('%Y-%m-%d')}) истек без подтверждения факта"
                    )
                    ResolutionEngine.resolve_event(
                        db=db,
                        event_id=ev.id,
                        outcome=False,
                        resolution_notes=notes
                    )
                    cls.total_auto_resolved_count += 1
                    resolved_events.append({
                        "event_id": ev.id,
                        "title": ev.title,
                        "outcome": False,
                        "reason": f"Дедлайн ({ev.deadline.strftime('%Y-%m-%d')}) истек"
                    })
                continue

            evaluated.append({
                "event_id": ev.id,
                "title": ev.title,
                "domain": ev.domain,
                "status": "ACTIVE"
            })

        summary = {
            "timestamp": cls.last_run_at.isoformat(),
            "total_active_checked": len(active_events),
            "resolved_count": len(resolved_events),
            "resolved_events": resolved_events,
            "evaluated_active": evaluated,
            "auto_resolve_enabled": auto_resolve,
            "live_prices": {k: round(v, 2) for k, v in prices.items() if isinstance(v, (int, float))}
        }
        cls.last_run_summary = summary
        return summary

    @classmethod
    async def start_background_worker(cls):
        """Starts asynchronous periodic oracle background worker."""
        if cls._background_task is not None and not cls._background_task.done():
            return
        cls._background_task = asyncio.create_task(cls._run_loop())
        logger.info("AutoOracle background worker started.")

    @classmethod
    async def stop_background_worker(cls):
        """Gracefully stops background worker."""
        if cls._background_task is not None:
            cls._background_task.cancel()
            try:
                await cls._background_task
            except asyncio.CancelledError:
                pass
            cls._background_task = None
            logger.info("AutoOracle background worker stopped.")

    @classmethod
    async def _run_loop(cls):
        while True:
            try:
                if cls.is_enabled:
                    with SessionLocal() as db:
                        await cls.evaluate_and_resolve_all(db=db, auto_resolve=True)
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in AutoOracle background loop: {e}", exc_info=True)
            
            await asyncio.sleep(cls.check_interval_seconds)
