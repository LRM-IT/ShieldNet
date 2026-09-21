import base64
import hashlib
import hmac
import json
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from uuid import uuid4

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.billing import BillingPayment, BillingPluginPlan, BillingSubscription, BillingWallet, BillingWalletTransaction
from app.services.billing_service import PAID_PACKAGE_KEY, normalize_plugin_key
from app.services.plugin_control_service import PluginControlService
from app.services.billing_discounts import BillingDiscountService


BILLING_VAULT_KEY = "core_billing"
PERIOD_DAYS = {"monthly": 30, "quarterly": 90, "yearly": 365}
PAYMENT_PROVIDER_FIELDS = {
    "liqpay": {"public": ("public_key",), "secret": ("private_key",)},
    "hutko": {"public": ("merchant_id",), "secret": ("secret_key",)},
    "tranzzo": {"public": ("pos_id",), "secret": ("api_key", "endpoints_key", "api_secret")},
    "payproglobal": {"public": ("product_id",), "secret": ("api_key", "webhook_secret")},
    "paddle": {"public": ("client_token", "monthly_price_id", "quarterly_price_id", "yearly_price_id"), "secret": ("api_key", "webhook_secret")},
    "fastspring": {"public": ("store_id", "monthly_product", "quarterly_product", "yearly_product"), "secret": ("api_username", "api_password", "webhook_secret")},
}
class PaymentError(ValueError):
    pass


def _money(value: Decimal) -> str:
    return f"{value:.2f}"


def _liqpay_signature(private_key: str, data: str) -> str:
    digest = hashlib.sha1(f"{private_key}{data}{private_key}".encode()).digest()
    return base64.b64encode(digest).decode()


class BillingPaymentService:
    def __init__(self, session: AsyncSession):
        self.session = session
        self.vault = PluginControlService(session)

    async def provider_config(self) -> dict:
        names = {x.secret_name for x in await self.vault.list_secrets(BILLING_VAULT_KEY)}
        result = {}
        for provider, fields in PAYMENT_PROVIDER_FIELDS.items():
            enabled_default = "true" if provider == "liqpay" else "false"
            enabled = (await self.vault.get_secret(BILLING_VAULT_KEY, f"{provider}_enabled") or enabled_default).lower() == "true"
            required = {f"{provider}_{name}" for name in (*fields["public"], *fields["secret"])}
            configured = required <= names
            item = {
                "enabled": enabled,
                "configured": configured,
                "active": enabled and configured,
                "secret_saved": {name: f"{provider}_{name}" in names for name in fields["secret"]},
            }
            for name in fields["public"]:
                item[name] = await self.vault.get_secret(BILLING_VAULT_KEY, f"{provider}_{name}") or ""
            result[provider] = item
        # Backwards-compatible flag used by the existing LiqPay form.
        result["liqpay"]["secret_saved"] = result["liqpay"]["secret_saved"]["private_key"]
        return result

    async def secret(self, name: str) -> str:
        value = await self.vault.get_secret(BILLING_VAULT_KEY, name)
        if not value:
            raise PaymentError("Payment provider is not configured")
        return value

    async def credit_wallet(self, discord_user_id: int, amount: Decimal, actor_id, comment: str | None = None) -> BillingWallet:
        wallet = (await self.session.execute(select(BillingWallet).where(
            BillingWallet.discord_user_id == discord_user_id, BillingWallet.currency == "USD"
        ).with_for_update())).scalar_one_or_none()
        if wallet is None:
            wallet = BillingWallet(id=uuid4(), discord_user_id=discord_user_id, balance=Decimal("0.00"), currency="USD")
            self.session.add(wallet); await self.session.flush()
        wallet.balance += amount
        self.session.add(BillingWalletTransaction(id=uuid4(), wallet_id=wallet.id, amount=amount,
            balance_after=wallet.balance, operation="admin_credit", comment=comment, actor_user_id=actor_id))
        await self.session.commit(); await self.session.refresh(wallet)
        return wallet

    async def create_wallet_topup(self, discord_user_id:int, amount:Decimal, provider:str, base_url:str) -> dict:
        config=await self.provider_config()
        if provider not in config or not config[provider]["active"]: raise PaymentError("Payment provider is disabled or not configured")
        charge_currency="USD";amount_usd=amount
        order=f"wallet-{discord_user_id}-{uuid4().hex}"
        payment=BillingPayment(id=uuid4(),order_reference=order,guild_id=None,plugin_key=None,billing_period=None,purpose="wallet_topup",owner_discord_id=discord_user_id,provider=provider,amount=amount,currency=charge_currency,base_amount_usd=amount_usd,original_amount_usd=amount_usd,quote_expires_at=datetime.now(timezone.utc)+timedelta(minutes=30))
        self.session.add(payment);await self.session.commit()
        product="GuildConsole software service account credit";callback=f"{base_url}/api/v1/billing/callback/{provider}";result=f"{base_url}/servers"
        public=await self.secret("liqpay_public_key");private=await self.secret("liqpay_private_key")
        payload={"version":"3","public_key":public,"action":"pay","amount":_money(amount),"currency":charge_currency,"description":product,"order_id":order,"server_url":callback,"result_url":result}
        data=base64.b64encode(json.dumps(payload,separators=(",", ":")).encode()).decode()
        return {"provider":provider,"action":"https://www.liqpay.ua/api/3/checkout","fields":{"data":data,"signature":_liqpay_signature(private,data)},"charge_amount":amount,"charge_currency":charge_currency}

    async def _complete(self,payment:BillingPayment,provider_id:str|None,raw:dict)->None:
        if payment.purpose!="wallet_topup":
            await self._activate(payment,provider_id,raw);return
        if payment.status=="paid": return
        wallet=(await self.session.execute(select(BillingWallet).where(BillingWallet.discord_user_id==payment.owner_discord_id,BillingWallet.currency=="USD").with_for_update())).scalar_one_or_none()
        if wallet is None:
            wallet=BillingWallet(id=uuid4(),discord_user_id=payment.owner_discord_id,balance=Decimal("0.00"),currency="USD");self.session.add(wallet);await self.session.flush()
        credit=payment.base_amount_usd or Decimal("0");wallet.balance+=credit
        self.session.add(BillingWalletTransaction(id=uuid4(),wallet_id=wallet.id,amount=credit,balance_after=wallet.balance,operation="gateway_topup",payment_id=payment.id,comment=payment.provider))
        payment.status="paid";payment.signature_verified=True;payment.provider_payment_id=provider_id;payment.raw_status=raw;payment.paid_at=datetime.now(timezone.utc)
        await self.session.commit()

    async def pay_from_wallet(self, guild_id: int, discord_user_id: int, plugin_key: str, period: str, auto_renew:bool=False) -> dict:
        key = PAID_PACKAGE_KEY
        if period not in PERIOD_DAYS:
            raise PaymentError("Unsupported plan")
        plan = (await self.session.execute(select(BillingPluginPlan).where(BillingPluginPlan.plugin_key == key))).scalar_one_or_none()
        original = getattr(plan, f"{period}_price", None) if plan and plan.enabled and not plan.is_free else None
        if original is None or original <= 0:
            raise PaymentError("Price is not configured for this period")
        discount=await BillingDiscountService(self.session).quote(guild_id,original);amount=discount["final"]
        if amount <= 0:
            payment = BillingPayment(id=uuid4(), order_reference=f"voucher-{guild_id}-{uuid4().hex}", guild_id=guild_id,
                plugin_key=key, billing_period=period, provider="voucher", amount=Decimal("0.00"), currency=plan.currency,
                status="created", signature_verified=True,purpose="subscription",owner_discord_id=discord_user_id, original_amount_usd=original, base_amount_usd=Decimal("0.00"),
                discount_percent=discount["total_percent"], discount_code=discount["card_code"])
            self.session.add(payment); await self.session.flush()
            await self._activate(payment, str(payment.id), {"source":"voucher","confirmed":True,"auto_renew":auto_renew})
            return {"provider":"voucher","order_reference":payment.order_reference,"status":"paid","balance":None,"currency":plan.currency}
        wallet = (await self.session.execute(select(BillingWallet).where(
            BillingWallet.discord_user_id == discord_user_id, BillingWallet.currency == plan.currency
        ).with_for_update())).scalar_one_or_none()
        if wallet is None or wallet.balance < amount:
            raise PaymentError("Insufficient account balance")
        payment = BillingPayment(id=uuid4(), order_reference=f"balance-{guild_id}-{uuid4().hex}", guild_id=guild_id,
            plugin_key=key, billing_period=period, provider="balance", amount=amount, currency=plan.currency,
            status="created", signature_verified=True,purpose="subscription",owner_discord_id=discord_user_id,original_amount_usd=original,base_amount_usd=amount,discount_percent=discount["total_percent"],discount_code=discount["card_code"])
        self.session.add(payment); await self.session.flush()
        wallet.balance -= amount
        self.session.add(BillingWalletTransaction(id=uuid4(), wallet_id=wallet.id, amount=-amount,
            balance_after=wallet.balance, operation="subscription_purchase", payment_id=payment.id,
            comment=f"{key} · {period}"))
        await self._activate(payment, str(payment.id), {"source":"wallet","confirmed":True,"auto_renew":auto_renew})
        return {"provider":"balance","order_reference":payment.order_reference,"status":"paid","balance":wallet.balance,"currency":wallet.currency}

    async def create_checkout(self, guild_id: int, plugin_key: str, period: str, provider: str, base_url: str) -> dict:
        key = PAID_PACKAGE_KEY
        if period not in PERIOD_DAYS or provider != "liqpay":
            raise PaymentError("Unsupported billing period or provider")
        config = await self.provider_config()
        if not config[provider]["active"]:
            raise PaymentError("Payment provider is disabled or not configured")
        plan = (await self.session.execute(select(BillingPluginPlan).where(BillingPluginPlan.plugin_key == key))).scalar_one_or_none()
        if plan is None or not plan.enabled or plan.is_free:
            raise PaymentError("Paid plan is unavailable")
        original_amount = getattr(plan, f"{period}_price")
        if original_amount is None or original_amount <= 0:
            raise PaymentError("Price is not configured for this period")
        discount=await BillingDiscountService(self.session).quote(guild_id,original_amount);base_amount=discount["final"]
        if base_amount <= 0:
            payment = BillingPayment(id=uuid4(), order_reference=f"voucher-{guild_id}-{uuid4().hex}", guild_id=guild_id,
                plugin_key=key, billing_period=period, provider="voucher", amount=Decimal("0.00"), currency="USD",
                status="created", signature_verified=True, original_amount_usd=original_amount, base_amount_usd=Decimal("0.00"),
                discount_percent=discount["total_percent"], discount_code=discount["card_code"])
            self.session.add(payment); await self.session.flush()
            await self._activate(payment, str(payment.id), {"source":"voucher","confirmed":True})
            return {"provider":"voucher","order_reference":payment.order_reference,"status":"paid","discount":discount}
        charge_currency="USD";amount=base_amount
        order = f"gc-{guild_id}-{uuid4().hex}"
        payment = BillingPayment(id=uuid4(), order_reference=order, guild_id=guild_id, plugin_key=key,
                                 billing_period=period, provider=provider, amount=amount, currency=charge_currency,
                                 original_amount_usd=original_amount,base_amount_usd=base_amount,discount_percent=discount["total_percent"],discount_code=discount["card_code"],quote_expires_at=datetime.now(timezone.utc)+timedelta(minutes=30))
        self.session.add(payment)
        await self.session.commit()
        product = f"GuildConsole software modules access - {period}"
        callback = f"{base_url}/api/v1/billing/callback/{provider}"
        result = f"{base_url}/guild/{guild_id}/billing"
        public = await self.secret("liqpay_public_key"); private = await self.secret("liqpay_private_key")
        payload = {"version":"3","public_key":public,"action":"pay","amount":_money(amount),"currency":charge_currency,
                   "description":product,"order_id":order,"server_url":callback,"result_url":result}
        data = base64.b64encode(json.dumps(payload, separators=(",", ":")).encode()).decode()
        return {"provider":provider,"order_reference":order,"action":"https://www.liqpay.ua/api/3/checkout","method":"POST",
                "fields":{"data":data,"signature":_liqpay_signature(private, data)},"charge_amount":amount,"charge_currency":charge_currency,
                "quote_minutes":30,"discount":discount}

    async def _activate(self, payment: BillingPayment, provider_id: str | None, raw: dict) -> None:
        if payment.status == "paid":
            return
        now = datetime.now(timezone.utc)
        subscription = (await self.session.execute(select(BillingSubscription).where(
            BillingSubscription.guild_id == payment.guild_id,
            BillingSubscription.plugin_key == payment.plugin_key,
        ).with_for_update())).scalar_one_or_none()
        days = PERIOD_DAYS[payment.billing_period]
        if subscription is None:
            subscription = BillingSubscription(id=uuid4(), guild_id=payment.guild_id, plugin_key=payment.plugin_key,
                status="active", billing_period=payment.billing_period, starts_at=now, expires_at=now + timedelta(days=days),
                provider=payment.provider, external_order_id=payment.order_reference,owner_discord_id=payment.owner_discord_id,auto_renew=bool(raw.get("auto_renew",False)))
            self.session.add(subscription)
        else:
            subscription.status = "active"; subscription.billing_period = payment.billing_period
            subscription.expires_at = max(subscription.expires_at, now) + timedelta(days=days)
            subscription.provider = payment.provider; subscription.external_order_id = payment.order_reference
            if payment.owner_discord_id: subscription.owner_discord_id=payment.owner_discord_id
            if "auto_renew" in raw: subscription.auto_renew=bool(raw["auto_renew"])
        payment.status = "paid"; payment.signature_verified = True; payment.provider_payment_id = provider_id
        payment.raw_status = raw; payment.paid_at = now
        await self.session.commit()

    async def confirm_liqpay(self, data: str, signature: str) -> None:
        private = await self.secret("liqpay_private_key"); public = await self.secret("liqpay_public_key")
        if not hmac.compare_digest(_liqpay_signature(private, data), signature):
            raise PaymentError("Invalid LiqPay signature")
        callback = json.loads(base64.b64decode(data).decode()); order = str(callback.get("order_id", ""))
        payment = (await self.session.execute(select(BillingPayment).where(BillingPayment.order_reference == order).with_for_update())).scalar_one_or_none()
        if payment is None or payment.provider != "liqpay":
            raise PaymentError("Unknown payment")
        status_payload = {"version":"3","public_key":public,"action":"status","order_id":order}
        status_data = base64.b64encode(json.dumps(status_payload, separators=(",", ":")).encode()).decode()
        async with httpx.AsyncClient(timeout=20) as client:
            response = await client.post("https://www.liqpay.ua/api/request", data={"data":status_data,"signature":_liqpay_signature(private,status_data)})
            response.raise_for_status(); verified = response.json()
        if verified.get("status") not in {"success", "sandbox"} or Decimal(str(verified.get("amount", 0))) != payment.amount or verified.get("currency") != payment.currency:
            payment.status = str(verified.get("status") or "rejected")[:32]; payment.raw_status = verified; await self.session.commit()
            raise PaymentError("LiqPay did not confirm the payment")
        await self._complete(payment, str(verified.get("payment_id") or ""), verified)
