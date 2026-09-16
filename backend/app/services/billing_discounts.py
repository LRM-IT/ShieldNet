from datetime import datetime, timezone
from decimal import Decimal, ROUND_HALF_UP
from uuid import uuid4
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.billing import BillingDiscountCard, BillingDiscountRedemption, BillingTenureDiscount
from app.models.discord import Guild

MAX_DISCOUNT = Decimal("50.00")

class DiscountError(ValueError): pass

class BillingDiscountService:
    def __init__(self, session: AsyncSession): self.session=session

    async def redeem(self, guild_id:int, code:str, user_id) -> BillingDiscountCard:
        now=datetime.now(timezone.utc); normalized=code.strip().upper()
        card=await self.session.scalar(select(BillingDiscountCard).where(BillingDiscountCard.code==normalized).with_for_update())
        if not card or not card.active or (card.valid_from and card.valid_from>now) or (card.valid_until and card.valid_until<=now): raise DiscountError("Discount card is invalid or expired")
        existing=await self.session.scalar(select(BillingDiscountRedemption).where(BillingDiscountRedemption.card_id==card.id,BillingDiscountRedemption.guild_id==guild_id))
        if existing: return card
        if card.max_redemptions is not None and card.redemptions>=card.max_redemptions: raise DiscountError("Discount card redemption limit reached")
        self.session.add(BillingDiscountRedemption(id=uuid4(),card_id=card.id,guild_id=guild_id,redeemed_by_user_id=user_id));card.redemptions+=1
        await self.session.commit();return card

    async def quote(self,guild_id:int,amount:Decimal)->dict:
        now=datetime.now(timezone.utc);guild=await self.session.get(Guild,guild_id)
        months=max(0,(now.year-guild.joined_at.year)*12+now.month-guild.joined_at.month-(1 if now.day<guild.joined_at.day else 0)) if guild else 0
        rules=list((await self.session.execute(select(BillingTenureDiscount).where(BillingTenureDiscount.active.is_(True),BillingTenureDiscount.minimum_months<=months).order_by(BillingTenureDiscount.minimum_months.desc()))).scalars())
        tenure=rules[0].percent if rules else Decimal("0")
        redemption=await self.session.execute(select(BillingDiscountCard,BillingDiscountRedemption).join(BillingDiscountRedemption,BillingDiscountRedemption.card_id==BillingDiscountCard.id).where(BillingDiscountRedemption.guild_id==guild_id,BillingDiscountCard.active.is_(True)).order_by(BillingDiscountCard.percent.desc()).limit(1))
        pair=redemption.first();card=pair[0] if pair and (not pair[0].valid_from or pair[0].valid_from<=now) and (not pair[0].valid_until or pair[0].valid_until>now) else None
        card_percent=card.percent if card else Decimal("0");total=min(MAX_DISCOUNT,tenure+card_percent)
        final=(amount*(Decimal("100")-total)/Decimal("100")).quantize(Decimal("0.01"),rounding=ROUND_HALF_UP)
        return {"original":amount,"final":final,"total_percent":total,"tenure_percent":tenure,"card_percent":card_percent,"card_code":card.code if card else None,"tenure_months":months}
