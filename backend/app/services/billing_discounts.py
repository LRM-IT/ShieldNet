from datetime import datetime, timezone
from decimal import Decimal, ROUND_HALF_UP
from uuid import uuid4
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.billing import BillingDiscountCard, BillingDiscountRedemption, BillingTenureDiscount, BillingWallet, BillingWalletTransaction
from app.models.discord import Guild

class DiscountError(ValueError): pass

class BillingDiscountService:
    def __init__(self, session: AsyncSession): self.session=session

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
