from datetime import datetime, timedelta, timezone
from decimal import Decimal
from uuid import UUID, uuid4

import httpx
from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import PlainTextResponse
from pydantic import BaseModel, EmailStr, Field, model_validator
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
from app.models.member_actions import MemberAction, MemberActionStatus, MemberActionType
from app.models.plugins import PluginRegistry
from app.services.billing_service import BillingService, PAID_PACKAGE_KEY, normalize_plugin_key
from app.services.billing_payments import BILLING_VAULT_KEY, BillingPaymentService, PaymentError, PaymentVerificationPending
from app.services.plugin_control_service import PluginControlService
from app.services.guild_plugin_service import GuildPluginService
from app.services.billing_discounts import BillingDiscountService, DiscountError
from app.services.email_delivery import EMAIL_VAULT_KEY, EmailDeliveryService
from app.services.public_exchange_rate import public_usd_uah_rate

router = APIRouter(tags=["Billing"])

def billing_message(locale:str|None,key:str,**values)->str:
    language=locale if locale in {"uk","ru"} else "en"
    messages={
        "dm_check":{"uk":"✅ GuildConsole: особисті повідомлення доступні. Нагадування про завершення підписки можуть надходити сюди.","ru":"✅ GuildConsole: личные сообщения доступны. Напоминания об окончании подписки могут приходить сюда.","en":"✅ GuildConsole: direct messages are available. Subscription expiry reminders can be delivered here."},
        "low_balance":{"uk":"⚠️ GuildConsole: ваш баланс становить {balance:.2f} USD і досяг установленого порога {threshold:.2f} USD.","ru":"⚠️ GuildConsole: ваш баланс составляет {balance:.2f} USD и достиг установленного порога {threshold:.2f} USD.","en":"⚠️ GuildConsole: your balance is {balance:.2f} USD and has reached the configured threshold of {threshold:.2f} USD."},
        "expiry":{"uk":"⏳ GuildConsole: підписка сервера «{name}» завершується {expires} UTC (залишилось приблизно {days} дн.).","ru":"⏳ GuildConsole: подписка сервера «{name}» заканчивается {expires} UTC (осталось примерно {days} дн.).","en":"⏳ GuildConsole: the subscription for “{name}” expires at {expires} UTC (approximately {days} days remaining)."},
    }
    return messages[key][language].format(**values)

def real_email(user:User|None)->str|None:
    if user is None or not user.email_verified or user.email.endswith("@users.guildconsole.invalid"):return None
    return user.email

class PlanUpdate(BaseModel):
    is_free: bool = False
    enabled: bool = True
    monthly_price: Decimal | None = Field(default=None, ge=0)
    quarterly_price: Decimal | None = Field(default=None, ge=0)
    yearly_price: Decimal | None = Field(default=None, ge=0)
    quarterly_discount_percent: Decimal = Field(default=0, ge=0, le=90)
    yearly_discount_percent: Decimal = Field(default=0, ge=0, le=90)

class GrantRequest(BaseModel):
    guild_id: int
    plugin_key: str
    billing_period: str = Field(pattern=r"^(monthly|quarterly|yearly|manual)$")
    days: int = Field(ge=1, le=3660)

class ProviderUpdate(BaseModel):
    liqpay_enabled: bool = True
    liqpay_public_key: str = ""
    liqpay_private_key: str = ""
    monobank_enabled: bool = False
    monobank_token: str = ""
    monobank_standard_enabled: bool = True
    monobank_subscription_enabled: bool = False
    monobank_subscription_interval: str = Field(default="1m", pattern=r"^(1m|3m|1y)$")
    monobank_hold_enabled: bool = False
    monobank_hold_validity_days: int = Field(default=9, ge=1, le=9)
    hutko_enabled: bool = False
    hutko_merchant_id: str = ""
    hutko_secret_key: str = ""
    tranzzo_enabled: bool = False
    tranzzo_pos_id: str = ""
    tranzzo_api_key: str = ""
    tranzzo_endpoints_key: str = ""
    tranzzo_api_secret: str = ""
    payproglobal_enabled: bool = False
    payproglobal_product_id: str = ""
    payproglobal_api_key: str = ""
    payproglobal_webhook_secret: str = ""
    paddle_enabled: bool = False
    paddle_client_token: str = ""
    paddle_api_key: str = ""
    paddle_webhook_secret: str = ""
    paddle_monthly_price_id: str = ""
    paddle_quarterly_price_id: str = ""
    paddle_yearly_price_id: str = ""
    fastspring_enabled: bool = False
    fastspring_store_id: str = ""
    fastspring_api_username: str = ""
    fastspring_api_password: str = ""
    fastspring_webhook_secret: str = ""
    fastspring_monthly_product: str = ""
    fastspring_quarterly_product: str = ""
    fastspring_yearly_product: str = ""

class CheckoutRequest(BaseModel):
    plugin_key: str
    billing_period: str = Field(pattern=r"^(monthly|quarterly|yearly|custom)$")
    provider: str = Field(pattern=r"^(liqpay|monobank)$")
    days: int | None = Field(default=None, ge=1, le=3660)
    locale: str = Field(default="en", pattern=r"^(en|uk|ru|de|fr|it|pl|ar)$")
class WalletTopupRequest(BaseModel):
    amount: Decimal = Field(gt=0, le=1_000_000)
    provider: str = Field(pattern=r"^liqpay$")
class SubscriptionPurchaseRequest(BaseModel):
    guild_id: int
    billing_period: str = Field(pattern=r"^(monthly|quarterly|yearly)$")
    auto_renew: bool = False
class WalletSettingsRequest(BaseModel):
    low_balance_enabled: bool = False
    low_balance_threshold: Decimal = Field(default=0, ge=0, le=1_000_000)
    low_balance_discord_dm: bool = True
    low_balance_email: bool = False
class SubscriptionReminderRequest(BaseModel):
    enabled: bool = False
    days_before: int = Field(default=3, ge=1, le=30)
    discord_dm: bool = True
    email: bool = False
class DmCheckRequest(BaseModel):
    guild_id: int
class EmailSettingsRequest(BaseModel):
    enabled: bool = False
    host: str = Field(default="",max_length=255)
    port: int = Field(default=587,ge=1,le=65535)
    username: str = Field(default="",max_length=320)
    password: str = Field(default="",max_length=500)
    from_email: str = Field(default="",max_length=320)
    from_name: str = Field(default="GuildConsole",max_length=160)
    use_tls: bool = True
    use_ssl: bool = False
class EmailTestRequest(BaseModel):
    recipient: EmailStr

class WalletCreditRequest(BaseModel):
    discord_user_id: int
    amount: Decimal = Field(gt=0, le=1_000_000)
    comment: str = Field(default="", max_length=500)
class DiscountCardIn(BaseModel):
    code:str=Field(min_length=3,max_length=64)
    amount_usd:Decimal|None=Field(default=None,gt=0,le=1_000_000)
    access_days:int|None=Field(default=None,ge=1,le=3660)
    active:bool=True
    valid_from:datetime|None=None;valid_until:datetime|None=None;max_redemptions:int|None=Field(default=None,ge=1)
    @model_validator(mode="after")
    def exactly_one_value(self):
        if (self.amount_usd is None) == (self.access_days is None):
            raise ValueError("Set either access days or a legacy USD voucher value")
        return self
class TenureDiscountIn(BaseModel):
    minimum_months:int=Field(ge=1,le=240);percent:Decimal=Field(gt=0,le=50);active:bool=True
class RedeemDiscountIn(BaseModel): code:str=Field(min_length=3,max_length=64)
class ServerVoucherIn(BaseModel):
    guild_id:int
    code:str=Field(min_length=3,max_length=64)

def plan_dict(row):
    return {"plugin_key":row.plugin_key,"is_free":row.is_free,"enabled":row.enabled,"currency":row.currency,
            "monthly_price":row.monthly_price,"quarterly_price":row.quarterly_price,"yearly_price":row.yearly_price,
            "quarterly_discount_percent":row.quarterly_discount_percent,"yearly_discount_percent":row.yearly_discount_percent}

def subscription_dict(row):
    return {"id":row.id,"guild_id":str(row.guild_id),"plugin_key":row.plugin_key,"status":row.status,"billing_period":row.billing_period,
            "starts_at":row.starts_at,"expires_at":row.expires_at,"provider":row.provider,"external_order_id":row.external_order_id,"auto_renew":row.auto_renew,
            "expiry_notice_enabled":row.expiry_notice_enabled,"expiry_notice_days":row.expiry_notice_days,"expiry_notice_discord_dm":row.expiry_notice_discord_dm,"expiry_notice_email":row.expiry_notice_email}

@router.get("/public/pricing")
async def public_pricing(session: AsyncSession = Depends(get_db_session)):
    row = await session.scalar(select(BillingPluginPlan).where(BillingPluginPlan.plugin_key == PAID_PACKAGE_KEY))
    configured = {x.plugin_key: x for x in await BillingService(session).list_plans()}
    plugins = list((await session.execute(select(PluginRegistry).order_by(PluginRegistry.name))).scalars())
    modules = []
    for plugin in plugins:
        key = normalize_plugin_key(plugin.plugin_key)
        module_plan = configured.get(key)
        modules.append({
            "plugin_key": key,
            "name": plugin.name,
            "description": plugin.description or "",
            "is_free": bool(module_plan.is_free) if module_plan else False,
            "enabled": bool(module_plan.enabled) if module_plan else True,
        })
    plan = None if row is None or not row.enabled or row.is_free else plan_dict(row)
    return {"currency": row.currency if row else "USD", "plan": plan, "modules": modules}

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
                "enabled": True, "currency": "USD", "monthly_price": None,
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
    row.is_free=False; row.enabled=payload.enabled; row.currency="USD"
    row.monthly_price=payload.monthly_price
    row.quarterly_discount_percent=payload.quarterly_discount_percent
    row.yearly_discount_percent=payload.yearly_discount_percent
    row.quarterly_price=(payload.monthly_price*Decimal("3")*(Decimal("100")-payload.quarterly_discount_percent)/Decimal("100")).quantize(Decimal("0.01")) if payload.monthly_price is not None else None
    row.yearly_price=(payload.monthly_price*Decimal("12")*(Decimal("100")-payload.yearly_discount_percent)/Decimal("100")).quantize(Decimal("0.01")) if payload.monthly_price is not None else None
    await session.commit(); await session.refresh(row); return plan_dict(row)

@router.put("/platform/billing/plans/{plugin_key}")
async def save_plan(plugin_key: str, payload: PlanUpdate, _: User = Depends(require_superadmin), session: AsyncSession = Depends(get_db_session)):
    key = normalize_plugin_key(plugin_key)
    row = (await session.execute(select(BillingPluginPlan).where(BillingPluginPlan.plugin_key == key))).scalar_one_or_none()
    if row is None:
        row = BillingPluginPlan(id=uuid4(), plugin_key=key)
        session.add(row)
    values = payload.model_dump()
    values["currency"] = "USD"
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
async def guild_billing(guild_id: int, user: User = Depends(get_current_user), session: AsyncSession = Depends(get_db_session)):
    await require_guild_management(session, user, guild_id)
    plans = await BillingService(session).list_plans(); subscriptions = await BillingService(session).list_subscriptions(guild_id)
    package = next((x for x in plans if x.plugin_key == PAID_PACKAGE_KEY), None)
    visible_plans = []
    if package and package.enabled:
        data=plan_dict(package); originals=[package.monthly_price,package.quarterly_price,package.yearly_price]; discounted=[]; discount_meta=None
        for amount in originals:
            if amount is None: discounted.append(None)
            else:
                q=await BillingDiscountService(session).quote(guild_id,amount);discounted.append(q["final"]);discount_meta=q
        data.update({"discounted_monthly_price":discounted[0],"discounted_quarterly_price":discounted[1],"discounted_yearly_price":discounted[2],"discount":discount_meta}); visible_plans=[data]
    tiers={x.plugin_key:("free" if x.is_free else "paid") for x in plans if x.plugin_key != PAID_PACKAGE_KEY}
    provider_config=await BillingPaymentService(session).provider_config();email_config=await EmailDeliveryService(session).public_config()
    uah_quote = None
    if provider_config.get("monobank", {}).get("active"):
        try:
            quote = await public_usd_uah_rate()
            uah_quote = {"rate": quote["rate"], "as_of": quote["as_of"], "stale": quote["stale"]}
        except (httpx.HTTPError, ValueError, TypeError, KeyError):
            pass
    return {"free_plugin_keys":sorted(x.plugin_key for x in plans if x.plugin_key != PAID_PACKAGE_KEY and x.is_free),"plans":visible_plans,"module_tiers":tiers,"subscriptions":[subscription_dict(x) for x in subscriptions if x.plugin_key == PAID_PACKAGE_KEY],
            "providers":{key:{"active":value["active"]} for key,value in provider_config.items()},
            "uah_quote":uah_quote,
            "email_available":bool(real_email(user)),"smtp_available":bool(email_config["enabled"] and email_config["configured"])}

@router.post("/billing/wallet/voucher")
async def redeem_voucher(payload:RedeemDiscountIn,user:User=Depends(get_current_user),session:AsyncSession=Depends(get_db_session)):
    raise HTTPException(410,"Balance vouchers are no longer available")
    if not user.discord_user_id: raise HTTPException(400,"Discord account is required")
    try: card,wallet=await BillingDiscountService(session).redeem_wallet(payload.code,user.id,user.discord_user_id)
    except DiscountError as exc: raise HTTPException(400,str(exc)) from exc
    return {"code":card.code,"amount_usd":card.amount_usd,"balance":wallet.balance,"currency":wallet.currency}

@router.post("/billing/server-voucher/preview")
async def preview_server_voucher(payload:ServerVoucherIn,user:User=Depends(get_current_user),session:AsyncSession=Depends(get_db_session)):
    guild=await session.get(Guild,payload.guild_id)
    if not user.discord_user_id or guild is None or guild.owner_discord_id!=user.discord_user_id:
        raise HTTPException(403,"Only the Discord server owner can use a voucher")
    try:
        card,days=await BillingDiscountService(session).server_voucher_days(payload.code,user.id,payload.guild_id)
        return {"code":card.code,"guild_id":str(payload.guild_id),"days":days}
    except (DiscountError,PaymentError) as exc:raise HTTPException(400,str(exc)) from exc

@router.post("/billing/server-voucher/redeem")
async def redeem_server_voucher(payload:ServerVoucherIn,user:User=Depends(get_current_user),session:AsyncSession=Depends(get_db_session)):
    guild=await session.get(Guild,payload.guild_id)
    if not user.discord_user_id or guild is None or guild.owner_discord_id!=user.discord_user_id:
        raise HTTPException(403,"Only the Discord server owner can use a voucher")
    try:return await BillingDiscountService(session).redeem_server_voucher(payload.code,user.id,user.discord_user_id,payload.guild_id)
    except (DiscountError,PaymentError) as exc:raise HTTPException(400,str(exc)) from exc

@router.post("/billing/wallet/checkout")
async def wallet_checkout(payload:WalletTopupRequest,request:Request,user:User=Depends(get_current_user),session:AsyncSession=Depends(get_db_session)):
    raise HTTPException(410,"Balance top-ups are no longer available")
    if not user.discord_user_id: raise HTTPException(400,"Discord account is required")
    try:return await BillingPaymentService(session).create_wallet_topup(user.discord_user_id,payload.amount,payload.provider,str(request.base_url).rstrip("/"))
    except PaymentError as exc:raise HTTPException(400,str(exc)) from exc

@router.post("/billing/subscriptions/purchase")
async def purchase_subscription(payload:SubscriptionPurchaseRequest,user:User=Depends(get_current_user),session:AsyncSession=Depends(get_db_session)):
    raise HTTPException(410,"Pay for the server subscription directly")
    guild=await session.get(Guild,payload.guild_id)
    if not user.discord_user_id or guild is None or guild.owner_discord_id!=user.discord_user_id:raise HTTPException(403,"Only the Discord server owner can purchase a subscription")
    try:return await BillingPaymentService(session).pay_from_wallet(payload.guild_id,user.discord_user_id,PAID_PACKAGE_KEY,payload.billing_period,payload.auto_renew)
    except PaymentError as exc:raise HTTPException(400,str(exc)) from exc

@router.put("/billing/wallet/settings")
async def wallet_settings(payload:WalletSettingsRequest,user:User=Depends(get_current_user),session:AsyncSession=Depends(get_db_session)):
    raise HTTPException(410,"Balance notifications are no longer available")
    if not user.discord_user_id:raise HTTPException(400,"Discord account is required")
    wallet=await session.scalar(select(BillingWallet).where(BillingWallet.discord_user_id==user.discord_user_id,BillingWallet.currency=="USD"))
    if wallet is None:wallet=BillingWallet(id=uuid4(),discord_user_id=user.discord_user_id,balance=Decimal("0.00"),currency="USD");session.add(wallet)
    if payload.low_balance_email and not real_email(user): raise HTTPException(422,"Email notifications require a verified email address in the user profile")
    email_config=await EmailDeliveryService(session).public_config()
    if payload.low_balance_email and not (email_config["enabled"] and email_config["configured"]):raise HTTPException(422,"Email delivery is not configured by the platform administrator")
    if payload.low_balance_enabled and not (payload.low_balance_discord_dm or payload.low_balance_email): raise HTTPException(422,"Select at least one notification channel")
    wallet.low_balance_enabled=payload.low_balance_enabled;wallet.low_balance_threshold=payload.low_balance_threshold
    wallet.low_balance_discord_dm=payload.low_balance_discord_dm;wallet.low_balance_email=payload.low_balance_email
    wallet.low_balance_notice_sent_at=None;wallet.low_balance_dm_notice_sent_at=None;wallet.low_balance_email_notice_sent_at=None
    await session.commit();return {"low_balance_enabled":wallet.low_balance_enabled,"low_balance_threshold":wallet.low_balance_threshold,"low_balance_discord_dm":wallet.low_balance_discord_dm,"low_balance_email":wallet.low_balance_email}

@router.put("/billing/subscriptions/{guild_id}/reminder")
async def subscription_reminder(guild_id:int,payload:SubscriptionReminderRequest,user:User=Depends(get_current_user),session:AsyncSession=Depends(get_db_session)):
    guild=await session.get(Guild,guild_id)
    if not user.discord_user_id or guild is None or guild.owner_discord_id!=user.discord_user_id:raise HTTPException(403,"Only the Discord server owner can change subscription reminders")
    if payload.email and not real_email(user):raise HTTPException(422,"Email notifications require a verified email address in the user profile")
    email_config=await EmailDeliveryService(session).public_config()
    if payload.email and not (email_config["enabled"] and email_config["configured"]):raise HTTPException(422,"Email delivery is not configured by the platform administrator")
    if payload.enabled and not (payload.discord_dm or payload.email):raise HTTPException(422,"Select at least one notification channel")
    row=await session.scalar(select(BillingSubscription).where(BillingSubscription.guild_id==guild_id,BillingSubscription.plugin_key==PAID_PACKAGE_KEY))
    if row is None:raise HTTPException(404,"Server subscription not found")
    row.expiry_notice_enabled=payload.enabled;row.expiry_notice_days=payload.days_before;row.expiry_notice_discord_dm=payload.discord_dm;row.expiry_notice_email=payload.email
    row.expiry_notice_sent_at=None;row.expiry_notice_for_expires_at=None;row.expiry_dm_notice_for_expires_at=None;row.expiry_email_notice_for_expires_at=None
    await session.commit();return subscription_dict(row)

@router.post("/billing/wallet/dm-check",status_code=202)
async def check_discord_dm(payload:DmCheckRequest,user:User=Depends(get_current_user),session:AsyncSession=Depends(get_db_session)):
    guild=await session.get(Guild,payload.guild_id)
    if not user.discord_user_id or guild is None or guild.owner_discord_id!=user.discord_user_id:raise HTTPException(403,"Only the Discord server owner can test direct messages")
    action=MemberAction(guild_id=guild.guild_id,discord_user_id=user.discord_user_id,action_type=MemberActionType.SEND_DM,payload={"message":billing_message(user.preferred_locale,"dm_check"),"source":"billing_dm_check"},requested_by=user.id)
    session.add(action);await session.commit();await session.refresh(action)
    return {"id":str(action.id),"status":action.status.value}

@router.get("/billing/wallet/dm-check/{action_id}")
async def discord_dm_check_status(action_id:UUID,user:User=Depends(get_current_user),session:AsyncSession=Depends(get_db_session)):
    action=await session.get(MemberAction,action_id)
    if action is None or action.requested_by!=user.id or action.payload.get("source")!="billing_dm_check":raise HTTPException(404,"DM check not found")
    return {"id":str(action.id),"status":action.status.value,"available":action.status==MemberActionStatus.COMPLETED,"message":action.result_message}

@router.get("/platform/billing/discounts")
async def discounts(_:User=Depends(require_superadmin),session:AsyncSession=Depends(get_db_session)):
    cards=list((await session.execute(select(BillingDiscountCard).order_by(BillingDiscountCard.created_at.desc()))).scalars())
    tenure=list((await session.execute(select(BillingTenureDiscount).order_by(BillingTenureDiscount.minimum_months))).scalars())
    return {"cards":[{"id":x.id,"code":x.code,"amount_usd":x.amount_usd,"access_days":x.access_days,"active":x.active,"valid_from":x.valid_from,"valid_until":x.valid_until,"max_redemptions":x.max_redemptions,"redemptions":x.redemptions} for x in cards],"tenure":[{"id":x.id,"minimum_months":x.minimum_months,"percent":x.percent,"active":x.active} for x in tenure],"maximum_combined_percent":50}

@router.post("/platform/billing/discounts/cards")
async def save_discount_card(payload:DiscountCardIn,_:User=Depends(require_superadmin),session:AsyncSession=Depends(get_db_session)):
    code=payload.code.strip().upper();row=await session.scalar(select(BillingDiscountCard).where(BillingDiscountCard.code==code))
    if row is None: row=BillingDiscountCard(id=uuid4(),code=code,redemptions=0);session.add(row)
    for k,v in payload.model_dump(exclude={"code"}).items():setattr(row,k,v)
    await session.commit();return {"id":row.id,"code":row.code,"amount_usd":row.amount_usd,"access_days":row.access_days,"active":row.active}

@router.put("/platform/billing/discounts/cards/{card_id}")
async def update_discount_card(card_id:UUID,payload:DiscountCardIn,_:User=Depends(require_superadmin),session:AsyncSession=Depends(get_db_session)):
    row=await session.get(BillingDiscountCard,card_id)
    if row is None:raise HTTPException(404,"Discount card not found")
    code=payload.code.strip().upper()
    duplicate=await session.scalar(select(BillingDiscountCard.id).where(BillingDiscountCard.code==code,BillingDiscountCard.id!=card_id))
    if duplicate:raise HTTPException(409,"Discount card code already exists")
    row.code=code
    for k,v in payload.model_dump(exclude={"code"}).items():setattr(row,k,v)
    await session.commit();return {"id":row.id,"code":row.code,"amount_usd":row.amount_usd,"access_days":row.access_days,"active":row.active}

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

@router.get("/platform/billing/providers")
async def providers(_: User = Depends(require_superadmin), session: AsyncSession = Depends(get_db_session)):
    return await BillingPaymentService(session).provider_config()

@router.put("/platform/billing/providers")
async def save_providers(payload: ProviderUpdate, user: User = Depends(require_superadmin), session: AsyncSession = Depends(get_db_session)):
    values = payload.model_dump()
    for name in tuple(values):
        if name.endswith("_enabled"):
            values[name] = "true" if values[name] else "false"
    vault = PluginControlService(session)
    for name, value in values.items():
        text = str(value).strip()
        if text:
            await vault.put_secret(BILLING_VAULT_KEY, name, text, "platform", "global", user.id)
    return await BillingPaymentService(session).provider_config()

@router.get("/platform/billing/email")
async def email_settings(_:User=Depends(require_superadmin),session:AsyncSession=Depends(get_db_session)):
    return await EmailDeliveryService(session).public_config()

@router.put("/platform/billing/email")
async def save_email_settings(payload:EmailSettingsRequest,user:User=Depends(require_superadmin),session:AsyncSession=Depends(get_db_session)):
    values={"enabled":"true" if payload.enabled else "false","host":payload.host,"port":str(payload.port),"username":payload.username,"password":payload.password,"from_email":payload.from_email,"from_name":payload.from_name,"use_tls":"true" if payload.use_tls else "false","use_ssl":"true" if payload.use_ssl else "false"}
    vault=PluginControlService(session)
    for name,value in values.items():
        if name=="password" and not value:continue
        await vault.put_secret(EMAIL_VAULT_KEY,name,value.strip(),"platform","global",user.id)
    return await EmailDeliveryService(session).public_config()

@router.post("/platform/billing/email/test")
async def test_email(payload:EmailTestRequest,_:User=Depends(require_superadmin),session:AsyncSession=Depends(get_db_session)):
    try:await EmailDeliveryService(session).send(str(payload.recipient),"GuildConsole SMTP test","GuildConsole SMTP is configured correctly. Billing email notifications can be delivered.")
    except Exception as exc:raise HTTPException(502,f"SMTP test failed: {exc}") from exc
    return {"delivered":True}

@router.get("/platform/billing/payments")
async def payments(_: User = Depends(require_superadmin), session: AsyncSession = Depends(get_db_session)):
    rows = list((await session.execute(select(BillingPayment).order_by(BillingPayment.created_at.desc()).limit(250))).scalars())
    guild_ids={x.guild_id for x in rows}
    guild_names={x.guild_id:x.name for x in (await session.execute(select(Guild).where(Guild.guild_id.in_(guild_ids)))).scalars()} if guild_ids else {}
    return [{"id":x.id,"order_reference":x.order_reference,"guild_id":str(x.guild_id),"guild_name":guild_names.get(x.guild_id),"plugin_key":x.plugin_key,
             "billing_period":x.billing_period,"provider":x.provider,"amount":x.amount,"currency":x.currency,
             "status":x.status,"signature_verified":x.signature_verified,"original_amount_usd":x.original_amount_usd,
             "discount_percent":x.discount_percent,"discount_code":x.discount_code,"paid_at":x.paid_at,"created_at":x.created_at} for x in rows]

@router.get("/platform/billing/wallets")
async def wallets(_: User = Depends(require_superadmin), session: AsyncSession = Depends(get_db_session)):
    owners = list((await session.execute(select(Guild.owner_discord_id).where(Guild.owner_discord_id > 0).distinct().order_by(Guild.owner_discord_id))).scalars())
    users = {x.discord_user_id:x for x in (await session.execute(select(User).where(User.discord_user_id.in_(owners)))).scalars()}
    balances = {x.discord_user_id:x for x in (await session.execute(select(BillingWallet).where(BillingWallet.discord_user_id.in_(owners)))).scalars()}
    return [{"discord_user_id":str(owner),"display_name":users.get(owner).display_name if users.get(owner) else None,
             "email":users.get(owner).email if users.get(owner) else None,"balance":balances.get(owner).balance if balances.get(owner) else Decimal("0.00"),
             "currency":balances.get(owner).currency if balances.get(owner) else "USD"} for owner in owners]

@router.post("/platform/billing/wallets/credit")
async def credit_wallet(payload: WalletCreditRequest, user: User = Depends(require_superadmin), session: AsyncSession = Depends(get_db_session)):
    raise HTTPException(410,"Balance credits are no longer available")
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

@router.get("/discord/guilds/{guild_id}/billing/quote")
async def custom_days_quote(guild_id: int, days: int = Query(ge=1, le=3660), user: User = Depends(get_current_user), session: AsyncSession = Depends(get_db_session)):
    await require_guild_management(session, user, guild_id)
    guild = await session.get(Guild, guild_id)
    if user.discord_user_id is None or guild is None or guild.owner_discord_id != user.discord_user_id:
        raise HTTPException(403, "Only the Discord server owner can purchase a subscription")
    try:
        return await BillingPaymentService(session).quote_days(guild_id, days)
    except PaymentError as exc:
        raise HTTPException(400, str(exc)) from exc

@router.post("/discord/guilds/{guild_id}/billing/checkout")
async def checkout(guild_id: int, payload: CheckoutRequest, request: Request, user: User = Depends(get_current_user), session: AsyncSession = Depends(get_db_session)):
    await require_guild_management(session, user, guild_id)
    guild = await session.get(Guild, guild_id)
    if user.discord_user_id is None or guild is None or guild.owner_discord_id != user.discord_user_id:
        raise HTTPException(403, "Only the Discord server owner can purchase a subscription")
    base_url = str(request.base_url).rstrip("/")
    try:
        return await BillingPaymentService(session).create_checkout(guild_id, payload.plugin_key, payload.billing_period, payload.provider, base_url, user.discord_user_id, payload.days, payload.locale)
    except PaymentError as exc:
        raise HTTPException(400, str(exc)) from exc

@router.post("/billing/callback/liqpay")
async def liqpay_callback(request: Request, session: AsyncSession = Depends(get_db_session)):
    from urllib.parse import parse_qs
    form = parse_qs((await request.body()).decode())
    try:
        await BillingPaymentService(session).confirm_liqpay(form.get("data", [""])[0], form.get("signature", [""])[0])
        return PlainTextResponse("OK")
    except (PaymentError, ValueError) as exc:
        return PlainTextResponse(str(exc), status_code=400)

@router.post("/billing/callback/monobank")
async def monobank_callback(request: Request, session: AsyncSession = Depends(get_db_session)):
    body = await request.body()
    if len(body) > 65536:
        raise HTTPException(413, "Webhook body is too large")
    try:
        await BillingPaymentService(session).confirm_monobank(body, request.headers.get("x-sign", ""))
    except PaymentError as exc:
        raise HTTPException(400, str(exc)) from exc
    except PaymentVerificationPending as exc:
        raise HTTPException(503, "Bank status is still updating") from exc
    except httpx.HTTPError as exc:
        raise HTTPException(503, "Payment confirmation temporarily unavailable") from exc
    return PlainTextResponse("OK")

@router.get("/billing/payments/{order_reference}/refresh")
async def refresh_checkout_payment(order_reference: str, user: User = Depends(get_current_user), session: AsyncSession = Depends(get_db_session)):
    payment = (await session.execute(select(BillingPayment).where(
        BillingPayment.order_reference == order_reference,
        BillingPayment.owner_discord_id == user.discord_user_id,
        BillingPayment.provider == "monobank",
    ).with_for_update())).scalar_one_or_none()
    if payment is None or not user.discord_user_id:
        raise HTTPException(404, "Payment not found")
    try:
        status = await BillingPaymentService(session).refresh_monobank(payment)
    except PaymentError as exc:
        raise HTTPException(409, str(exc)) from exc
    except httpx.HTTPError as exc:
        raise HTTPException(503, "Payment confirmation temporarily unavailable") from exc
    return {"status": status, "order_reference": payment.order_reference}

@router.post("/internal/billing/reconcile", dependencies=[Depends(verify_internal_service_token)])
async def reconcile_billing(session: AsyncSession = Depends(get_db_session)):
    now=datetime.now(timezone.utc)
    expired = await BillingService(session).expired_enabled_plugins()
    disabled = []
    for guild_id, plugin_key in expired:
        try:
            await GuildPluginService(session).set_enabled(guild_id, plugin_key, False)
            disabled.append({"guild_id":guild_id,"plugin_key":plugin_key})
        except LookupError:
            continue
    queued=[]
    reminders=list((await session.execute(select(BillingSubscription).where(BillingSubscription.status=="active",BillingSubscription.expiry_notice_enabled.is_(True),BillingSubscription.expires_at>now,BillingSubscription.expires_at<=now+timedelta(days=30)))).scalars())
    for item in reminders:
        if item.expires_at>now+timedelta(days=item.expiry_notice_days):continue
        guild=await session.get(Guild,item.guild_id);owner_id=item.owner_discord_id or (guild.owner_discord_id if guild else None)
        name=guild.name if guild else str(item.guild_id);days=max(0,(item.expires_at-now).days);owner=await session.scalar(select(User).where(User.discord_user_id==owner_id)) if owner_id else None
        message=billing_message(owner.preferred_locale if owner else None,"expiry",name=name,expires=f"{item.expires_at:%Y-%m-%d %H:%M}",days=days)
        if item.expiry_notice_discord_dm and owner_id and item.expiry_dm_notice_for_expires_at!=item.expires_at:
            session.add(MemberAction(guild_id=item.guild_id,discord_user_id=owner_id,action_type=MemberActionType.SEND_DM,payload={"message":billing_message(owner.preferred_locale if owner else None,"expiry",name=name,expires=f"{item.expires_at:%Y-%m-%d %H:%M}",days=days),"source":"subscription_expiry_reminder"},requested_by=None))
            queued.append({"type":"subscription_expiry_dm","guild_id":str(item.guild_id)});item.expiry_dm_notice_for_expires_at=item.expires_at
        email=real_email(owner)
        if item.expiry_notice_email and email and item.expiry_email_notice_for_expires_at!=item.expires_at:
            try:await EmailDeliveryService(session).send(email,"GuildConsole: server subscription expiry",message);item.expiry_email_notice_for_expires_at=item.expires_at;queued.append({"type":"subscription_expiry_email","guild_id":str(item.guild_id)})
            except Exception:pass
        if item.expiry_dm_notice_for_expires_at==item.expires_at or item.expiry_email_notice_for_expires_at==item.expires_at:item.expiry_notice_sent_at=now;item.expiry_notice_for_expires_at=item.expires_at
    await session.commit()
    return {"count":len(disabled),"disabled":disabled,"renewed":[],"notifications":queued}
