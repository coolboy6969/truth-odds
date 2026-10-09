from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from pydantic import BaseModel
from app.database.session import get_db
from app.oracles.auto_oracle import AutoOracleService
from app.oracles.crypto_oracle import CryptoPriceOracle

router = APIRouter(prefix="/api/oracle", tags=["Auto Oracle & Verification"])

class ToggleRequest(BaseModel):
    enabled: bool

@router.get("/status")
def get_oracle_status():
    return {
        "is_enabled": AutoOracleService.is_enabled,
        "check_interval_seconds": AutoOracleService.check_interval_seconds,
        "last_run_at": AutoOracleService.last_run_at.isoformat() if AutoOracleService.last_run_at else None,
        "total_auto_resolved": AutoOracleService.total_auto_resolved_count,
        "last_summary": AutoOracleService.last_run_summary
    }

@router.post("/toggle")
def toggle_oracle(payload: ToggleRequest):
    AutoOracleService.is_enabled = payload.enabled
    return {
        "success": True,
        "is_enabled": AutoOracleService.is_enabled,
        "message": f"Автопроверка {'включена' if payload.enabled else 'приостановлена'}"
    }

@router.post("/check-now")
async def check_now(auto_resolve: bool = True, db: Session = Depends(get_db)):
    """
    Executes an immediate verification check across all active predictions against live market data.
    """
    summary = await AutoOracleService.evaluate_and_resolve_all(db=db, auto_resolve=auto_resolve)
    return {
        "success": True,
        "summary": summary
    }

@router.get("/prices")
async def get_live_prices():
    prices = await CryptoPriceOracle.get_live_prices()
    return prices
