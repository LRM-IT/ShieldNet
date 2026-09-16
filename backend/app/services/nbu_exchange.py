from datetime import datetime, timedelta, timezone
from decimal import Decimal, ROUND_HALF_UP
from uuid import uuid4

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.billing import BillingExchangeRate

NBU_URL = "https://bank.gov.ua/NBUStatService/v1/statdirectory/exchangenew?json"
SUPPORTED_DISPLAY_CURRENCIES = ("UAH", "USD", "EUR", "PLN", "GBP", "CAD", "CHF", "CZK", "RON", "TRY", "SAR", "AED")

class ExchangeRateError(ValueError):
    pass

class NBUExchangeService:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def refresh_if_stale(self) -> None:
        newest = await self.session.scalar(select(BillingExchangeRate.updated_at).order_by(BillingExchangeRate.updated_at.desc()).limit(1))
        if newest and newest > datetime.now(timezone.utc) - timedelta(hours=6):
            return
        try:
            async with httpx.AsyncClient(timeout=15, follow_redirects=True) as client:
                response = await client.get(NBU_URL); response.raise_for_status(); payload = response.json()
        except (httpx.HTTPError, ValueError):
            if newest: return
            raise ExchangeRateError("NBU exchange rates are temporarily unavailable")
        now = datetime.now(timezone.utc)
        for item in payload:
            currency = str(item.get("cc", "")).upper()
            if currency not in SUPPORTED_DISPLAY_CURRENCIES or not item.get("rate"):
                continue
            try: effective = datetime.strptime(item["exchangedate"], "%d.%m.%Y").replace(tzinfo=timezone.utc)
            except (KeyError, ValueError): effective = now
            row = await self.session.scalar(select(BillingExchangeRate).where(BillingExchangeRate.currency == currency))
            if row is None:
                row = BillingExchangeRate(id=uuid4(), currency=currency, uah_per_unit=Decimal(str(item["rate"])), effective_date=effective)
                self.session.add(row)
            else:
                row.uah_per_unit = Decimal(str(item["rate"])); row.effective_date = effective; row.updated_at = now
        await self.session.commit()

    async def rate(self, currency: str) -> tuple[Decimal, datetime]:
        code = currency.upper()
        if code == "UAH": return Decimal("1"), datetime.now(timezone.utc)
        if code not in SUPPORTED_DISPLAY_CURRENCIES: raise ExchangeRateError("Unsupported display currency")
        await self.refresh_if_stale()
        row = await self.session.scalar(select(BillingExchangeRate).where(BillingExchangeRate.currency == code))
        if row is None: raise ExchangeRateError("NBU does not provide this currency rate")
        return row.uah_per_unit, row.effective_date

    async def convert_from_uah(self, amount: Decimal | None, currency: str) -> Decimal | None:
        if amount is None: return None
        rate, _ = await self.rate(currency)
        return (amount / rate).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)

    async def quote(self, amounts: list[Decimal | None], currency: str) -> tuple[list[Decimal | None], datetime]:
        rate, effective = await self.rate(currency)
        return [None if x is None else (x / rate).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP) for x in amounts], effective
