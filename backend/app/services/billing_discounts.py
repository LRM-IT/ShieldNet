from datetime import datetime, timezone
from decimal import Decimal, ROUND_HALF_UP
from uuid import uuid4
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.billing import BillingDiscountCard, BillingDiscountRedemption, BillingTenureDiscount, BillingWallet, BillingWalletTransaction, BillingPayment
from app.models.discord import Guild

class DiscountError(ValueError): pass

class BillingDiscountService:
    def __init__(self, session: AsyncSession): self.session=session

    async def server_voucher_days(self, code: str, user_id, guild_id: int, *, lock: bool = False, plugin_key: str = "__paid_modules__") -> tuple[BillingDiscountCard, int]:
        normalized = code.strip().upper()
        query = select(BillingDiscountCard).where(BillingDiscountCard.code == normalized)
        if lock: query = query.with_for_update()
        card = await self.session.scalar(query)
        now = datetime.now(timezone.utc)
        if not card or not card.active or (card.valid_from and card.valid_from > now) or (card.valid_until and card.valid_until <= now):
            raise DiscountError("Voucher is invalid or expired")
        if card.plugin_key != plugin_key:
            raise DiscountError("Voucher is intended for another subscription")
        used = await self.session.scalar(select(BillingDiscountRedemption.id).where(BillingDiscountRedemption.card_id == card.id, BillingDiscountRedemption.redeemed_by_user_id == user_id))
        if used: raise DiscountError("Voucher has already been redeemed")
        if card.max_redemptions is not None and card.redemptions >= card.max_redemptions:
            raise DiscountError("Voucher redemption limit reached")
        if card.access_days:
            return card, card.access_days
        if not card.amount_usd or card.amount_usd <= 0:
            raise DiscountError("Voucher has no subscription value")
        # Existing USD vouchers become server access, without creating a personal balance.
        from app.services.billing_payments import BillingPaymentService
        billing = BillingPaymentService(self.session)
        max_quote = await billing.quote_days(guild_id, 3660)
        if card.amount_usd > max_quote["total_amount"]:
            raise DiscountError("Voucher value exceeds the maximum subscription period; contact support")
        best = 1
        for first, last in ((1, 89), (90, 364), (365, 3660)):
            if (await billing.quote_days(guild_id, first))["total_amount"] > card.amount_usd: continue
            low, high = first, last
            while low <= high:
                middle = (low + high) // 2
                if (await billing.quote_days(guild_id, middle))["total_amount"] <= card.amount_usd:
                    best = max(best, middle); low = middle + 1
                else:
                    high = middle - 1
        if (await billing.quote_days(guild_id, best))["total_amount"] >= card.amount_usd:
            return card, best
        # Round up to a whole access day so the holder never loses voucher value.
        for first, last in ((1, 89), (90, 364), (365, 3660)):
            low, high = max(first, best + 1), last
            if low > high or (await billing.quote_days(guild_id, high))["total_amount"] < card.amount_usd: continue
            while low < high:
                middle = (low + high) // 2
                if (await billing.quote_days(guild_id, middle))["total_amount"] >= card.amount_usd: high = middle
                else: low = middle + 1
            return card, low
        raise DiscountError("Voucher value exceeds the maximum subscription period; contact support")

    async def redeem_server_voucher(self, code: str, user_id, owner_discord_id: int, guild_id: int, plugin_key: str = "__paid_modules__") -> dict:
        card, days = await self.server_voucher_days(code, user_id, guild_id, lock=True, plugin_key=plugin_key)
        from app.services.billing_payments import BillingPaymentService
        quote = await BillingPaymentService(self.session).quote_days(guild_id, days)
        payment = BillingPayment(id=uuid4(), order_reference=f"voucher-{guild_id}-{uuid4().hex}", guild_id=guild_id,
            plugin_key=plugin_key, billing_period="custom", access_days=days, purpose="subscription", owner_discord_id=owner_discord_id,
            provider="voucher", amount=Decimal("0.00"), currency="USD", status="created", signature_verified=True,
            original_amount_usd=quote["total_amount"], base_amount_usd=Decimal("0.00"), discount_code=card.code)
        self.session.add(payment)
        self.session.add(BillingDiscountRedemption(id=uuid4(), card_id=card.id, guild_id=guild_id, redeemed_by_user_id=user_id))
        card.redemptions += 1
        await self.session.flush()
        await BillingPaymentService(self.session)._activate(payment, str(payment.id), {"source":"server_voucher", "code":card.code, "confirmed":True})
        return {"guild_id": str(guild_id), "days": days, "status": "paid", "order_reference": payment.order_reference}

    async def redeem_wallet(self, code:str, user_id, discord_user_id:int) -> tuple[BillingDiscountCard, BillingWallet]:
        now=datetime.now(timezone.utc); normalized=code.strip().upper()
        card=await self.session.scalar(select(BillingDiscountCard).where(BillingDiscountCard.code==normalized).with_for_update())
        if not card or not card.amount_usd or not card.active or (card.valid_from and card.valid_from>now) or (card.valid_until and card.valid_until<=now): raise DiscountError("Voucher is invalid or expired")
        existing=await self.session.scalar(select(BillingDiscountRedemption).where(BillingDiscountRedemption.card_id==card.id,BillingDiscountRedemption.redeemed_by_user_id==user_id))
        if existing: raise DiscountError("Voucher has already been redeemed")
        if card.max_redemptions is not None and card.redemptions>=card.max_redemptions: raise DiscountError("Voucher redemption limit reached")
        wallet=await self.session.scalar(select(BillingWallet).where(BillingWallet.discord_user_id==discord_user_id,BillingWallet.currency=="USD").with_for_update())
        if wallet is None:
            wallet=BillingWallet(id=uuid4(),discord_user_id=discord_user_id,balance=Decimal("0.00"),currency="USD");self.session.add(wallet);await self.session.flush()
        amount=card.amount_usd;wallet.balance+=amount
        self.session.add(BillingDiscountRedemption(id=uuid4(),card_id=card.id,guild_id=None,redeemed_by_user_id=user_id))
        self.session.add(BillingWalletTransaction(id=uuid4(),wallet_id=wallet.id,amount=amount,balance_after=wallet.balance,operation="voucher_credit",comment=f"Voucher {card.code}"))
        card.redemptions+=1
        await self.session.commit();return card,wallet

    async def quote(self,guild_id:int,amount:Decimal)->dict:
        now=datetime.now(timezone.utc);guild=await self.session.get(Guild,guild_id)
        months=max(0,(now.year-guild.joined_at.year)*12+now.month-guild.joined_at.month-(1 if now.day<guild.joined_at.day else 0)) if guild else 0
        rules=list((await self.session.execute(select(BillingTenureDiscount).where(BillingTenureDiscount.active.is_(True),BillingTenureDiscount.minimum_months<=months).order_by(BillingTenureDiscount.minimum_months.desc()))).scalars())
        tenure=rules[0].percent if rules else Decimal("0")
        total=tenure
        final=(amount*(Decimal("100")-tenure)/Decimal("100")).quantize(Decimal("0.01"),rounding=ROUND_HALF_UP)
        return {"original":amount,"final":final,"total_percent":total,"tenure_percent":tenure,"card_percent":Decimal("0"),"fixed_amount_usd":Decimal("0"),"card_type":None,"card_code":None,"tenure_months":months}
