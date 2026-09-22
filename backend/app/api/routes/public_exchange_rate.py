from fastapi import APIRouter, HTTPException

from app.services.public_exchange_rate import public_usd_uah_rate

router = APIRouter(tags=["Public exchange rate"])


@router.get("/public/exchange-rate")
async def exchange_rate() -> dict:
    try:
        return await public_usd_uah_rate()
    except Exception as exc:
        raise HTTPException(status_code=503, detail="Exchange rate temporarily unavailable") from exc
