from datetime import datetime, timedelta, timezone
from decimal import Decimal
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import JSONResponse, PlainTextResponse
from pydantic import BaseModel, Field, model_validator
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies.auth import get_current_user
from app.api.dependencies.guild_access import require_guild_management
from app.api.dependencies.platform_access import require_superadmin
from app.api.dependencies.internal import verify_internal_service_token
from app.db.session import get_db_session
from app.models.billing import BillingPluginPlan, BillingSubscription, BillingPayment, BillingWallet, BillingWalletTransaction, BillingDiscountCard, BillingTenureDiscount
from app.models.core import User
from app.models.discord import Guild
from app.models.plugins import PluginRegistry
from app.services.billing_service import BillingService, PAID_PACKAGE_KEY, normalize_plugin_key
from app.services.billing_payments import BILLING_VAULT_KEY, BillingPaymentService, PaymentError
from app.services.plugin_control_service import PluginControlService
from app.services.guild_plugin_service import GuildPluginService
from app.services.nbu_exchange import NBUExchangeService, ExchangeRateError, SUPPORTED_DISPLAY_CURRENCIES
from app.services.billing_discounts import BillingDiscountService, DiscountError

router = APIRouter(tags=["Billing"])

class PlanUpdate(BaseModel):
    is_free: bool = False
    enabled: bool = True
    currency: str = Field(default="UAH", pattern=r"^[A-Z]{3}$")
    monthly_price: Decimal | None = Field(default=None, ge=0)
    quarterly_price: Decimal | None = Field(default=None, ge=0)
    yearly_price: Decimal | None = Field(default=None, ge=0)

class GrantRequest(BaseModel):
    guild_id: int
    plugin_key: str
    billing_period: str = Field(pattern=r"^(monthly|quarterly|yearly|manual)$")
    days: int = Field(ge=1, le=3660)

class ProviderUpdate(BaseModel):
    wayforpay_enabled: bool = True
    wayforpay_merchant_account: str = ""
    wayforpay_merchant_domain: str = ""
    wayforpay_secret_key: str = ""
    liqpay_enabled: bool = True
    liqpay_public_key: str = ""
    liqpay_private_key: str = ""

class CheckoutRequest(BaseModel):
    plugin_key: str
    billing_period: str = Field(pattern=r"^(monthly|quarterly|yearly)$")
    provider: str = Field(pattern=r"^(wayforpay|liqpay|balance)$")
    display_currency: str = Field(default="UAH", pattern=r"^[A-Z]{3}$")

class WalletCreditRequest(BaseModel):
    discord_user_id: int
    amount: Decimal = Field(gt=0, le=1_000_000)
    comment: str = Field(default="", max_length=500)
class DiscountCardIn(BaseModel):
    code:str=Field(min_length=3,max_length=64);discount_type:str=Field(default="percent",pattern=r"^(percent|fixed)$")
    percent:Decimal=Field(default=10,ge=0,le=50);amount_uah:Decimal|None=Field(default=None,gt=0,le=1_000_000);active:bool=True
    valid_from:datetime|None=None;valid_until:datetime|None=None;max_redemptions:int|None=Field(default=None,ge=1)
    @model_validator(mode="after")
    def validate_value(self):
        if self.discount_type == "percent":
            if self.percent <= 0: raise ValueError("Percentage discount must be greater than zero")
            self.amount_uah = None
        elif self.amount_uah is None:
            raise ValueError("Voucher amount must be greater than zero")
        else:
            self.percent = Decimal("0")
        return self
class TenureDiscountIn(BaseModel):
    minimum_months:int=Field(ge=1,le=240);percent:Decimal=Field(gt=0,le=50);active:bool=True
class RedeemDiscountIn(BaseModel): code:str=Field(min_length=3,max_length=64)

def plan_dict(row):
    return {"plugin_key":row.plugin_key,"is_free":row.is_free,"enabled":row.enabled,"currency":row.currency,
            "monthly_price":row.monthly_price,"quarterly_price":row.quarterly_price,"yearly_price":row.yearly_price}

def subscription_dict(row):
    return {"id":row.id,"guild_id":str(row.guild_id),"plugin_key":row.plugin_key,"status":row.status,"billing_period":row.billing_period,
            "starts_at":row.starts_at,"expires_at":row.expires_at,"provider":row.provider,"external_order_id":row.external_order_id}

@router.get("/platform/billing/plans")
async def plans(_: User = Depends(require_superadmin), session: AsyncSession = Depends(get_db_session)):
    configured = {x.plugin_key: x for x in await BillingService(session).list_plans()}
    plugins = list((await session.execute(select(PluginRegistry).order_by(PluginRegistry.name))).scalars())
    result = []
    for plugin in plugins:
        key = normalize_plugin_key(plugin.plugin_key)
        row = configured.get(key)
        if row:
            data = plan_dict(row)
            data["name"] = plugin.name
            result.append(data)
        else:
            result.append({
                "plugin_key": key, "name": plugin.name, "is_free": False,
                "enabled": True, "currency": "UAH", "monthly_price": None,
                "quarterly_price": None, "yearly_price": None,
            })
    return result

@router.get("/platform/billing/package")
async def paid_package(_: User = Depends(require_superadmin), session: AsyncSession = Depends(get_db_session)):
    row = await session.scalar(select(BillingPluginPlan).where(BillingPluginPlan.plugin_key == PAID_PACKAGE_KEY))
    return plan_dict(row)

@router.put("/platform/billing/package")
async def save_paid_package(payload: PlanUpdate, _: User = Depends(require_superadmin), session: AsyncSession = Depends(get_db_session)):
    row = await session.scalar(select(BillingPluginPlan).where(BillingPluginPlan.plugin_key == PAID_PACKAGE_KEY))
    if row is None:
        row = BillingPluginPlan(id=uuid4(), plugin_key=PAID_PACKAGE_KEY, is_free=False); session.add(row)
    row.is_free=False; row.enabled=payload.enabled; row.currency="UAH"
    row.monthly_price=payload.monthly_price; row.quarterly_price=payload.quarterly_price; row.yearly_price=payload.yearly_price
    await session.commit(); await session.refresh(row); return plan_dict(row)

@router.put("/platform/billing/plans/{plugin_key}")
async def save_plan(plugin_key: str, payload: PlanUpdate, _: User = Depends(require_superadmin), session: AsyncSession = Depends(get_db_session)):
    key = normalize_plugin_key(plugin_key)
    row = (await session.execute(select(BillingPluginPlan).where(BillingPluginPlan.plugin_key == key))).scalar_one_or_none()
    if row is None:
        row = BillingPluginPlan(id=uuid4(), plugin_key=key)
        session.add(row)
    values = payload.model_dump()
    values["currency"] = "UAH"
    for field, value in values.items(): setattr(row, field, value)
    await session.commit(); await session.refresh(row)
    return plan_dict(row)

@router.get("/platform/billing/subscriptions")
async def subscriptions(guild_id: int | None = None, _: User = Depends(require_superadmin), session: AsyncSession = Depends(get_db_session)):
    return [subscription_dict(x) for x in await BillingService(session).list_subscriptions(guild_id)]

@router.post("/platform/billing/subscriptions/grant")
async def grant(payload: GrantRequest, user: User = Depends(require_superadmin), session: AsyncSession = Depends(get_db_session)):
    key = PAID_PACKAGE_KEY; now = datetime.now(timezone.utc)
    row = (await session.execute(select(BillingSubscription).where(BillingSubscription.guild_id == payload.guild_id, BillingSubscription.plugin_key == key))).scalar_one_or_none()
    if row is None:
        row = BillingSubscription(id=uuid4(), guild_id=payload.guild_id, plugin_key=key, billing_period=payload.billing_period,
                                  starts_at=now, expires_at=now + timedelta(days=payload.days), granted_by_user_id=user.id)
        session.add(row)
    else:
        row.status="active"; row.billing_period=payload.billing_period; row.starts_at=now; row.expires_at=max(row.expires_at, now)+timedelta(days=payload.days); row.granted_by_user_id=user.id
    await session.commit(); await session.refresh(row)
    return subscription_dict(row)

@router.delete("/platform/billing/subscriptions/{subscription_id}")
async def revoke(subscription_id: UUID, _: User = Depends(require_superadmin), session: AsyncSession = Depends(get_db_session)):
    row = await session.get(BillingSubscription, subscription_id)
    if row is None: raise HTTPException(404, "Subscription not found")
    row.status="revoked"; await session.commit()
    return subscription_dict(row)

@router.get("/discord/guilds/{guild_id}/billing")
async def guild_billing(guild_id: int, display_currency: str = "UAH", user: User = Depends(get_current_user), session: AsyncSession = Depends(get_db_session)):
    await require_guild_management(session, user, guild_id)
    plans = await BillingService(session).list_plans(); subscriptions = await BillingService(session).list_subscriptions(guild_id)
    wallet = await session.scalar(select(BillingWallet).where(BillingWallet.discord_user_id == user.discord_user_id)) if user.discord_user_id else None
    try:
        rate, effective = await NBUExchangeService(session).rate(display_currency)
    except ExchangeRateError as exc:
        raise HTTPException(503, str(exc)) from exc
    package = next((x for x in plans if x.plugin_key == PAID_PACKAGE_KEY), None)
    visible_plans = []
    if package and package.enabled:
        data=plan_dict(package); originals=[package.monthly_price,package.quarterly_price,package.yearly_price]; discounted=[]; discount_meta=None
        for amount in originals:
            if amount is None: discounted.append(None)
            else:
                q=await BillingDiscountService(session).quote(guild_id,amount);discounted.append(q["final"]);discount_meta=q
        values,_=await NBUExchangeService(session).quote(discounted,display_currency)
        data.update({"display_currency":display_currency.upper(),"display_monthly_price":values[0],"display_quarterly_price":values[1],"display_yearly_price":values[2],"discounted_monthly_price":discounted[0],"discounted_quarterly_price":discounted[1],"discounted_yearly_price":discounted[2],"discount":discount_meta}); visible_plans=[data]
    tiers={x.plugin_key:("free" if x.is_free else "paid") for x in plans if x.plugin_key != PAID_PACKAGE_KEY}
    provider_config=await BillingPaymentService(session).provider_config()
    return {"free_plugin_keys":sorted(x.plugin_key for x in plans if x.plugin_key != PAID_PACKAGE_KEY and x.is_free),"plans":visible_plans,"module_tiers":tiers,"subscriptions":[subscription_dict(x) for x in subscriptions if x.plugin_key == PAID_PACKAGE_KEY],
            "providers":{key:{"active":value["active"]} for key,value in provider_config.items()},
            "exchange_rate":{"base":"UAH","currency":display_currency.upper(),"uah_per_unit":rate,"effective_at":effective,"source":"NBU"},
            "wallet":{"balance":wallet.balance,"currency":wallet.currency} if wallet else {"balance":Decimal("0.00"),"currency":"UAH"}}

@router.post("/discord/guilds/{guild_id}/billing/discount-card")
async def redeem_discount(guild_id:int,payload:RedeemDiscountIn,user:User=Depends(get_current_user),session:AsyncSession=Depends(get_db_session)):
    await require_guild_management(session,user,guild_id)
    try: card=await BillingDiscountService(session).redeem(guild_id,payload.code,user.id)
    except DiscountError as exc: raise HTTPException(400,str(exc)) from exc
    return {"code":card.code,"discount_type":card.discount_type,"percent":card.percent,"amount_uah":card.amount_uah,"active":card.active}

@router.get("/platform/billing/discounts")
async def discounts(_:User=Depends(require_superadmin),session:AsyncSession=Depends(get_db_session)):
    cards=list((await session.execute(select(BillingDiscountCard).order_by(BillingDiscountCard.created_at.desc()))).scalars())
    tenure=list((await session.execute(select(BillingTenureDiscount).order_by(BillingTenureDiscount.minimum_months))).scalars())
    return {"cards":[{"id":x.id,"code":x.code,"discount_type":x.discount_type,"percent":x.percent,"amount_uah":x.amount_uah,"active":x.active,"valid_from":x.valid_from,"valid_until":x.valid_until,"max_redemptions":x.max_redemptions,"redemptions":x.redemptions} for x in cards],"tenure":[{"id":x.id,"minimum_months":x.minimum_months,"percent":x.percent,"active":x.active} for x in tenure],"maximum_combined_percent":50}

@router.post("/platform/billing/discounts/cards")
async def save_discount_card(payload:DiscountCardIn,_:User=Depends(require_superadmin),session:AsyncSession=Depends(get_db_session)):
    code=payload.code.strip().upper();row=await session.scalar(select(BillingDiscountCard).where(BillingDiscountCard.code==code))
    if row is None: row=BillingDiscountCard(id=uuid4(),code=code,redemptions=0);session.add(row)
    for k,v in payload.model_dump(exclude={"code"}).items():setattr(row,k,v)
    await session.commit();return {"id":row.id,"code":row.code,"discount_type":row.discount_type,"percent":row.percent,"amount_uah":row.amount_uah,"active":row.active}

@router.put("/platform/billing/discounts/cards/{card_id}")
async def update_discount_card(card_id:UUID,payload:DiscountCardIn,_:User=Depends(require_superadmin),session:AsyncSession=Depends(get_db_session)):
    row=await session.get(BillingDiscountCard,card_id)
    if row is None:raise HTTPException(404,"Discount card not found")
    code=payload.code.strip().upper()
    duplicate=await session.scalar(select(BillingDiscountCard.id).where(BillingDiscountCard.code==code,BillingDiscountCard.id!=card_id))
    if duplicate:raise HTTPException(409,"Discount card code already exists")
    row.code=code
    for k,v in payload.model_dump(exclude={"code"}).items():setattr(row,k,v)
    await session.commit();return {"id":row.id,"code":row.code,"discount_type":row.discount_type,"percent":row.percent,"amount_uah":row.amount_uah,"active":row.active}

@router.delete("/platform/billing/discounts/cards/{card_id}")
async def delete_discount_card(card_id:UUID,_:User=Depends(require_superadmin),session:AsyncSession=Depends(get_db_session)):
    row=await session.get(BillingDiscountCard,card_id)
    if row is None:raise HTTPException(404,"Discount card not found")
    await session.delete(row);await session.commit();return {"deleted":True,"id":card_id}

@router.post("/platform/billing/discounts/tenure")
async def save_tenure_discount(payload:TenureDiscountIn,_:User=Depends(require_superadmin),session:AsyncSession=Depends(get_db_session)):
    row=await session.scalar(select(BillingTenureDiscount).where(BillingTenureDiscount.minimum_months==payload.minimum_months))
    if row is None:row=BillingTenureDiscount(id=uuid4(),minimum_months=payload.minimum_months);session.add(row)
    row.percent=payload.percent;row.active=payload.active;await session.commit();return {"id":row.id,"minimum_months":row.minimum_months,"percent":row.percent,"active":row.active}

@router.put("/platform/billing/discounts/tenure/{rule_id}")
async def update_tenure_discount(rule_id:UUID,payload:TenureDiscountIn,_:User=Depends(require_superadmin),session:AsyncSession=Depends(get_db_session)):
    row=await session.get(BillingTenureDiscount,rule_id)
    if row is None:raise HTTPException(404,"Loyalty rule not found")
    duplicate=await session.scalar(select(BillingTenureDiscount.id).where(BillingTenureDiscount.minimum_months==payload.minimum_months,BillingTenureDiscount.id!=rule_id))
    if duplicate:raise HTTPException(409,"A loyalty rule for this number of months already exists")
    row.minimum_months=payload.minimum_months;row.percent=payload.percent;row.active=payload.active
    await session.commit();return {"id":row.id,"minimum_months":row.minimum_months,"percent":row.percent,"active":row.active}

@router.delete("/platform/billing/discounts/tenure/{rule_id}")
async def delete_tenure_discount(rule_id:UUID,_:User=Depends(require_superadmin),session:AsyncSession=Depends(get_db_session)):
    row=await session.get(BillingTenureDiscount,rule_id)
    if row is None:raise HTTPException(404,"Loyalty rule not found")
    await session.delete(row);await session.commit();return {"deleted":True,"id":rule_id}

@router.get("/billing/exchange-rates")
async def exchange_rates(_: User = Depends(get_current_user), session: AsyncSession = Depends(get_db_session)):
    service = NBUExchangeService(session)
    try: await service.refresh_if_stale()
    except ExchangeRateError as exc: raise HTTPException(503, str(exc)) from exc
    result = []
    for currency in SUPPORTED_DISPLAY_CURRENCIES:
        try:
            rate, effective = await service.rate(currency)
            result.append({"currency":currency,"uah_per_unit":rate,"effective_at":effective,"source":"NBU"})
        except ExchangeRateError: continue
    return result

@router.get("/platform/billing/providers")
async def providers(_: User = Depends(require_superadmin), session: AsyncSession = Depends(get_db_session)):
    return await BillingPaymentService(session).provider_config()

@router.put("/platform/billing/providers")
async def save_providers(payload: ProviderUpdate, user: User = Depends(require_superadmin), session: AsyncSession = Depends(get_db_session)):
    values = {
        "wfp_enabled": "true" if payload.wayforpay_enabled else "false",
        "wfp_merchant_account": payload.wayforpay_merchant_account,
        "wfp_merchant_domain": payload.wayforpay_merchant_domain,
        "wfp_secret_key": payload.wayforpay_secret_key,
        "liqpay_enabled": "true" if payload.liqpay_enabled else "false",
        "liqpay_public_key": payload.liqpay_public_key,
        "liqpay_private_key": payload.liqpay_private_key,
    }
    vault = PluginControlService(session)
    for name, value in values.items():
        if value.strip():
            await vault.put_secret(BILLING_VAULT_KEY, name, value.strip(), "platform", "global", user.id)
    return await BillingPaymentService(session).provider_config()

@router.get("/platform/billing/payments")
async def payments(_: User = Depends(require_superadmin), session: AsyncSession = Depends(get_db_session)):
    rows = list((await session.execute(select(BillingPayment).order_by(BillingPayment.created_at.desc()).limit(250))).scalars())
    guild_ids={x.guild_id for x in rows}
    guild_names={x.guild_id:x.name for x in (await session.execute(select(Guild).where(Guild.guild_id.in_(guild_ids)))).scalars()} if guild_ids else {}
    return [{"id":x.id,"order_reference":x.order_reference,"guild_id":str(x.guild_id),"guild_name":guild_names.get(x.guild_id),"plugin_key":x.plugin_key,
             "billing_period":x.billing_period,"provider":x.provider,"amount":x.amount,"currency":x.currency,
             "status":x.status,"signature_verified":x.signature_verified,"original_amount_uah":x.original_amount_uah,
             "discount_percent":x.discount_percent,"discount_code":x.discount_code,"paid_at":x.paid_at,"created_at":x.created_at} for x in rows]

@router.get("/platform/billing/wallets")
async def wallets(_: User = Depends(require_superadmin), session: AsyncSession = Depends(get_db_session)):
    owners = list((await session.execute(select(Guild.owner_discord_id).where(Guild.owner_discord_id > 0).distinct().order_by(Guild.owner_discord_id))).scalars())
    users = {x.discord_user_id:x for x in (await session.execute(select(User).where(User.discord_user_id.in_(owners)))).scalars()}
    balances = {x.discord_user_id:x for x in (await session.execute(select(BillingWallet).where(BillingWallet.discord_user_id.in_(owners)))).scalars()}
    return [{"discord_user_id":str(owner),"display_name":users.get(owner).display_name if users.get(owner) else None,
             "email":users.get(owner).email if users.get(owner) else None,"balance":balances.get(owner).balance if balances.get(owner) else Decimal("0.00"),
             "currency":balances.get(owner).currency if balances.get(owner) else "UAH"} for owner in owners]

@router.post("/platform/billing/wallets/credit")
async def credit_wallet(payload: WalletCreditRequest, user: User = Depends(require_superadmin), session: AsyncSession = Depends(get_db_session)):
    if payload.discord_user_id <= 0:
        raise HTTPException(400, "A real Discord owner is required")
    owns_guild = await session.scalar(select(Guild.guild_id).where(Guild.owner_discord_id == payload.discord_user_id).limit(1))
    if owns_guild is None:
        raise HTTPException(404, "Discord user is not an owner of a registered server")
    wallet = await BillingPaymentService(session).credit_wallet(payload.discord_user_id, payload.amount, user.id, payload.comment.strip() or None)
    return {"discord_user_id":str(wallet.discord_user_id),"balance":wallet.balance,"currency":wallet.currency}

@router.get("/platform/billing/wallets/{discord_user_id}/transactions")
async def wallet_transactions(discord_user_id: int, _: User = Depends(require_superadmin), session: AsyncSession = Depends(get_db_session)):
    wallet = await session.scalar(select(BillingWallet).where(BillingWallet.discord_user_id == discord_user_id))
    if wallet is None: return []
    rows = list((await session.execute(select(BillingWalletTransaction).where(BillingWalletTransaction.wallet_id == wallet.id).order_by(BillingWalletTransaction.created_at.desc()).limit(250))).scalars())
    return [{"id":x.id,"amount":x.amount,"balance_after":x.balance_after,"operation":x.operation,"comment":x.comment,
             "actor_user_id":x.actor_user_id,"created_at":x.created_at} for x in rows]

@router.post("/discord/guilds/{guild_id}/billing/checkout")
async def checkout(guild_id: int, payload: CheckoutRequest, request: Request, user: User = Depends(get_current_user), session: AsyncSession = Depends(get_db_session)):
    await require_guild_management(session, user, guild_id)
    if payload.provider == "balance":
        guild = await session.get(Guild, guild_id)
        if user.discord_user_id is None or guild is None or guild.owner_discord_id != user.discord_user_id:
            raise HTTPException(403, "Only the Discord server owner can spend the owner balance")
        try:
            return await BillingPaymentService(session).pay_from_wallet(guild_id, user.discord_user_id, payload.plugin_key, payload.billing_period)
        except PaymentError as exc:
            raise HTTPException(400, str(exc)) from exc
    base_url = str(request.base_url).rstrip("/")
    try:
        return await BillingPaymentService(session).create_checkout(guild_id, payload.plugin_key, payload.billing_period, payload.provider, base_url, payload.display_currency)
    except PaymentError as exc:
        raise HTTPException(400, str(exc)) from exc

@router.post("/billing/callback/wayforpay")
async def wayforpay_callback(request: Request, session: AsyncSession = Depends(get_db_session)):
    try:
        payload = await request.json()
        return await BillingPaymentService(session).confirm_wayforpay(payload)
    except PaymentError as exc:
        return JSONResponse({"detail":str(exc)}, status_code=400)

@router.post("/billing/callback/liqpay")
async def liqpay_callback(request: Request, session: AsyncSession = Depends(get_db_session)):
    from urllib.parse import parse_qs
    form = parse_qs((await request.body()).decode())
    try:
        await BillingPaymentService(session).confirm_liqpay(form.get("data", [""])[0], form.get("signature", [""])[0])
        return PlainTextResponse("OK")
    except (PaymentError, ValueError) as exc:
        return PlainTextResponse(str(exc), status_code=400)

@router.post("/internal/billing/reconcile", dependencies=[Depends(verify_internal_service_token)])
async def reconcile_billing(session: AsyncSession = Depends(get_db_session)):
    expired = await BillingService(session).expired_enabled_plugins()
    disabled = []
    for guild_id, plugin_key in expired:
        try:
            await GuildPluginService(session).set_enabled(guild_id, plugin_key, False)
            disabled.append({"guild_id":guild_id,"plugin_key":plugin_key})
        except LookupError:
            continue
    return {"count":len(disabled),"disabled":disabled}
