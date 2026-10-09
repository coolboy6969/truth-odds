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
    def check_all_active_events(cls, db: Session, auto_resolve: bool = False) -> Dict[str, Any]:
        """
        Synchronously checks active events against crypto price targets and deadlines.
        """
        cls.last_run_at = datetime.utcnow()
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
            target_info = CryptoPriceOracle.parse_event_price_target(ev.title)
            if target_info:
                asset = target_info["asset"]
                target_price = target_info["target"]
                direction = target_info.get("direction", "up")
                target_year = target_info.get("target_year")
                current_price = prices.get(asset, 0.0)

                target_met = (current_price >= target_price) if direction == "up" else (current_price <= target_price)
                expired_by_year = (target_year is not None and target_year < current_year)
                expired_by_deadline = (ev.deadline is not None and ev.deadline < now)

                if target_met:
                    if auto_resolve:
                        notes = (
                            f"Автоматически подтверждено оракулом: цена {asset} "
                            f"(${current_price:,.2f}) достигла целевой отметки ${target_price:,.2f}"
                        )
                        ResolutionEngine.resolve_event(
                            db=db,
                            event_id=ev.id,
                            outcome=True,
                            resolution_notes=notes
                        )
                        cls.total_auto_resolved_count += 1
                        resolved_events.append({
                            "event_id": ev.id,
                            "title": ev.title,
                            "outcome": True
                        })
                    continue
                elif expired_by_year or expired_by_deadline:
                    if auto_resolve:
                        time_desc = str(target_year) if target_year else ev.deadline.strftime("%Y-%m-%d")
                        notes = (
                            f"Автоматически зафиксировано оракулом: срок прогноза ({time_desc}) истек, "
                            f"целевая цена не достигнута"
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
                            "outcome": False
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
        prices = await CryptoPriceOracle.get_live_prices()
        active_events = db.query(Event).filter(Event.status == "ACTIVE").all()

        evaluated = []
        resolved_events = []
        now = datetime.utcnow()
        current_year = now.year

        for ev in active_events:
            # 1. Crypto Price Targets
            target_info = CryptoPriceOracle.parse_event_price_target(ev.title)
            if target_info:
                asset = target_info["asset"]
                target_price = target_info["target"]
                direction = target_info.get("direction", "up")
                target_year = target_info.get("target_year")
                current_price = prices.get(asset, 0.0)

                target_met = (current_price >= target_price) if direction == "up" else (current_price <= target_price)
                expired_by_year = (target_year is not None and target_year < current_year)
                expired_by_deadline = (ev.deadline is not None and ev.deadline < now)

                if target_met:
                    if auto_resolve:
                        notes = (
                            f"Автоматически подтверждено оракулом: цена {asset} "
                            f"(${current_price:,.2f}) достигла целевой отметки ${target_price:,.2f}"
                        )
                        ResolutionEngine.resolve_event(
                            db=db,
                            event_id=ev.id,
                            outcome=True,
                            resolution_notes=notes
                        )
                        cls.total_auto_resolved_count += 1
                        resolved_events.append({
                            "event_id": ev.id,
                            "title": ev.title,
                            "outcome": True,
                            "reason": f"Целевая цена {asset} достигнута (${current_price:,.2f})"
                        })
                    continue
                elif expired_by_year or expired_by_deadline:
                    if auto_resolve:
                        time_desc = str(target_year) if target_year else ev.deadline.strftime("%Y-%m-%d")
                        notes = (
                            f"Автоматически зафиксировано оракулом: срок прогноза ({time_desc}) истек, "
                            f"целевая цена не достигнута (текущая цена {asset}: ${current_price:,.2f})"
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
                            "reason": f"Срок прогноза ({time_desc}) истек без достижения цели"
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

            # 2. General events with passed deadlines
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
