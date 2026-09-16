from datetime import datetime, timedelta, timezone
from decimal import Decimal
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import JSONResponse, PlainTextResponse
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies.auth import get_current_user
from app.api.dependencies.guild_access import require_guild_management
from app.api.dependencies.platform_access import require_superadmin
from app.db.session import get_db_session
from app.models.billing import BillingPluginPlan, BillingSubscription, BillingPayment
from app.models.core import User
from app.models.plugins import PluginRegistry
from app.services.billing_service import BillingService, FREE_PLUGIN_KEYS, normalize_plugin_key
from app.services.billing_payments import BILLING_VAULT_KEY, BillingPaymentService, PaymentError
from app.services.plugin_control_service import PluginControlService

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
    wayforpay_merchant_account: str = ""
    wayforpay_merchant_domain: str = ""
    wayforpay_secret_key: str = ""
    liqpay_public_key: str = ""
    liqpay_private_key: str = ""

class CheckoutRequest(BaseModel):
    plugin_key: str
    billing_period: str = Field(pattern=r"^(monthly|quarterly|yearly)$")
    provider: str = Field(pattern=r"^(wayforpay|liqpay)$")

def plan_dict(row):
    return {"plugin_key":row.plugin_key,"is_free":row.is_free,"enabled":row.enabled,"currency":row.currency,
            "monthly_price":row.monthly_price,"quarterly_price":row.quarterly_price,"yearly_price":row.yearly_price}

def subscription_dict(row):
    return {"id":row.id,"guild_id":row.guild_id,"plugin_key":row.plugin_key,"status":row.status,"billing_period":row.billing_period,
            "starts_at":row.starts_at,"expires_at":row.expires_at,"provider":row.provider,"external_order_id":row.external_order_id}

@router.get("/platform/billing/plans")
async def plans(_: User = Depends(require_superadmin), session: AsyncSession = Depends(get_db_session)):
    configured = {x.plugin_key: x for x in await BillingService(session).list_plans()}
    plugins = list((await session.execute(select(PluginRegistry).order_by(PluginRegistry.name))).scalars())
    result = []
    for plugin in plugins:
        key = normalize_plugin_key(plugin.plugin_key)
        row = configured.get(key)
        result.append(plan_dict(row) if row else {
            "plugin_key": key, "name": plugin.name, "is_free": key in FREE_PLUGIN_KEYS,
            "enabled": True, "currency": "UAH", "monthly_price": None,
            "quarterly_price": None, "yearly_price": None,
        })
    return result

@router.put("/platform/billing/plans/{plugin_key}")
async def save_plan(plugin_key: str, payload: PlanUpdate, _: User = Depends(require_superadmin), session: AsyncSession = Depends(get_db_session)):
    key = normalize_plugin_key(plugin_key)
    row = (await session.execute(select(BillingPluginPlan).where(BillingPluginPlan.plugin_key == key))).scalar_one_or_none()
    if row is None:
        row = BillingPluginPlan(id=uuid4(), plugin_key=key)
        session.add(row)
    values = payload.model_dump()
    if key in FREE_PLUGIN_KEYS:
        values["is_free"] = True
    for field, value in values.items(): setattr(row, field, value)
    await session.commit(); await session.refresh(row)
    return plan_dict(row)

@router.get("/platform/billing/subscriptions")
async def subscriptions(guild_id: int | None = None, _: User = Depends(require_superadmin), session: AsyncSession = Depends(get_db_session)):
    return [subscription_dict(x) for x in await BillingService(session).list_subscriptions(guild_id)]

@router.post("/platform/billing/subscriptions/grant")
async def grant(payload: GrantRequest, user: User = Depends(require_superadmin), session: AsyncSession = Depends(get_db_session)):
    key = normalize_plugin_key(payload.plugin_key); now = datetime.now(timezone.utc)
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
    return {"free_plugin_keys":sorted(FREE_PLUGIN_KEYS),"plans":[plan_dict(x) for x in plans if x.enabled],"subscriptions":[subscription_dict(x) for x in subscriptions]}

@router.get("/platform/billing/providers")
async def providers(_: User = Depends(require_superadmin), session: AsyncSession = Depends(get_db_session)):
    return await BillingPaymentService(session).provider_config()

@router.put("/platform/billing/providers")
async def save_providers(payload: ProviderUpdate, user: User = Depends(require_superadmin), session: AsyncSession = Depends(get_db_session)):
    values = {
        "wfp_merchant_account": payload.wayforpay_merchant_account,
        "wfp_merchant_domain": payload.wayforpay_merchant_domain,
        "wfp_secret_key": payload.wayforpay_secret_key,
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
    return [{"id":x.id,"order_reference":x.order_reference,"guild_id":x.guild_id,"plugin_key":x.plugin_key,
             "billing_period":x.billing_period,"provider":x.provider,"amount":x.amount,"currency":x.currency,
             "status":x.status,"signature_verified":x.signature_verified,"paid_at":x.paid_at,"created_at":x.created_at} for x in rows]

@router.post("/discord/guilds/{guild_id}/billing/checkout")
async def checkout(guild_id: int, payload: CheckoutRequest, request: Request, user: User = Depends(get_current_user), session: AsyncSession = Depends(get_db_session)):
    await require_guild_management(session, user, guild_id)
    base_url = str(request.base_url).rstrip("/")
    try:
        return await BillingPaymentService(session).create_checkout(guild_id, payload.plugin_key, payload.billing_period, payload.provider, base_url)
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
