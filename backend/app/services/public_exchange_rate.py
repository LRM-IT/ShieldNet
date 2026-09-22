"""Cached public USD/UAH quotation for display, not payment settlement."""
from __future__ import annotations

import asyncio
from datetime import UTC, datetime, timedelta
from decimal import Decimal, InvalidOperation

import httpx

MONOBANK_CURRENCY_URL = "https://api.monobank.ua/bank/currency"
_lock = asyncio.Lock()
_cached: dict | None = None
_expires_at = datetime.min.replace(tzinfo=UTC)


def _parse_usd_uah(rows: list[dict]) -> dict:
    for row in rows:
        if row.get("currencyCodeA") != 840 or row.get("currencyCodeB") != 980:
            continue
        try:
            rate = Decimal(str(row.get("rateSell") or row.get("rateCross")))
            quoted_at = datetime.fromtimestamp(int(row["date"]), UTC)
        except (InvalidOperation, ValueError, TypeError, KeyError, OverflowError) as exc:
            raise ValueError("Invalid USD/UAH quotation") from exc
        if not rate.is_finite() or rate <= 0 or rate > 1000:
            raise ValueError("Invalid USD/UAH rate")
        if quoted_at > datetime.now(UTC) + timedelta(minutes=10) or quoted_at < datetime.now(UTC) - timedelta(days=2):
            raise ValueError("Outdated USD/UAH quotation")
        return {"base": "USD", "quote": "UAH", "rate": float(rate), "as_of": quoted_at.isoformat(), "source": "monobank", "stale": False}
    raise ValueError("USD/UAH quotation unavailable")


async def public_usd_uah_rate() -> dict:
    global _cached, _expires_at
    now = datetime.now(UTC)
    if _cached is not None and now < _expires_at:
        return _cached
    async with _lock:
        now = datetime.now(UTC)
        if _cached is not None and now < _expires_at:
            return _cached
        try:
            async with httpx.AsyncClient(timeout=8) as client:
                response = await client.get(MONOBANK_CURRENCY_URL)
                response.raise_for_status()
                quote = _parse_usd_uah(response.json())
        except (httpx.HTTPError, ValueError, TypeError):
            # Keep a recent quote through a short provider outage; never invent a rate.
            if _cached is not None and datetime.fromisoformat(_cached["as_of"]) > now - timedelta(days=1):
                _expires_at = now + timedelta(minutes=5)
                return {**_cached, "stale": True}
            raise
        _cached = quote
        _expires_at = now + timedelta(minutes=5)
        return quote
