import base64
import binascii
import hashlib
import hmac
import json
import logging
from urllib.parse import urlparse
from datetime import datetime, timedelta, timezone
from decimal import Decimal, ROUND_HALF_UP
from uuid import uuid4

import httpx
from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ec
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.billing import BillingPayment, BillingPluginPlan, BillingSubscription, BillingWallet, BillingWalletTransaction
from app.services.billing_service import PAID_PACKAGE_KEY, normalize_plugin_key
from app.services.plugin_control_service import PluginControlService
from app.services.billing_discounts import BillingDiscountService
from app.services.public_exchange_rate import public_usd_uah_rate

logger = logging.getLogger(__name__)

BILLING_VAULT_KEY = "core_billing"
PERIOD_DAYS = {"monthly": 30, "quarterly": 90, "yearly": 365}
PAYMENT_PROVIDER_FIELDS = {
    "liqpay": {"public": ("public_key",), "secret": ("private_key",)},
    "monobank": {"public": (), "secret": ("token",)},
    "hutko": {"public": ("merchant_id",), "secret": ("secret_key",)},
    "tranzzo": {"public": ("pos_id",), "secret": ("api_key", "endpoints_key", "api_secret")},
    "payproglobal": {"public": ("product_id",), "secret": ("api_key", "webhook_secret")},
    "paddle": {"public": ("client_token", "monthly_price_id", "quarterly_price_id", "yearly_price_id"), "secret": ("api_key", "webhook_secret")},
    "fastspring": {"public": ("store_id", "monthly_product", "quarterly_product", "yearly_product"), "secret": ("api_username", "api_password", "webhook_secret")},
}
class PaymentError(ValueError):
    pass


class PaymentVerificationPending(RuntimeError):
    pass


_monobank_pubkeys: dict[str, tuple[object, datetime]] = {}
MONOBANK_CHECKOUT_HOSTS = {"pay.mbnk.biz", "pay.monobank.ua"}


def _monobank_checkout_text(locale: str, guild_id: int, days: int) -> dict[str, str]:
    templates = {
        "uk": ("Доступ до GuildConsole", "Доступ до модулів сервера {guild} на {days} днів"),
        "ru": ("Доступ к GuildConsole", "Доступ к модулям сервера {guild} на {days} дней"),
        "en": ("GuildConsole access", "Access to modules for server {guild} for {days} days"),
        "de": ("GuildConsole-Zugang", "Zugang zu den Modulen für Server {guild} für {days} Tage"),
        "fr": ("Accès à GuildConsole", "Accès aux modules du serveur {guild} pendant {days} jours"),
        "it": ("Accesso a GuildConsole", "Accesso ai moduli del server {guild} per {days} giorni"),
        "pl": ("Dostęp do GuildConsole", "Dostęp do modułów serwera {guild} przez {days} dni"),
        "ar": ("الوصول إلى GuildConsole", "الوصول إلى وحدات الخادم {guild} لمدة {days} يومًا"),
    }
    name, destination = templates.get(locale, templates["en"])
    return {"name": name, "destination": destination.format(guild=guild_id, days=days)}


def _monobank_amount(amount_usd: Decimal, rate: float) -> Decimal:
    amount = (amount_usd * Decimal(str(rate))).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    if amount < Decimal("0.01") or amount > Decimal("100000000.00"):
        raise PaymentError("Converted payment amount is invalid")
    return amount


def _monobank_confirmed(status: dict, payment: BillingPayment) -> bool:
    expected_kopecks = int((payment.amount * 100).to_integral_exact())
    return (status.get("status") == "success"
            and status.get("invoiceId") == payment.provider_payment_id
            and status.get("reference") == payment.order_reference
            and status.get("ccy") == 980
            and status.get("amount") == expected_kopecks)


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
        monobank_standard = (await self.vault.get_secret(BILLING_VAULT_KEY, "monobank_standard_enabled") or "true").lower() == "true"
        monobank_subscription = (await self.vault.get_secret(BILLING_VAULT_KEY, "monobank_subscription_enabled") or "false").lower() == "true"
        monobank_hold = (await self.vault.get_secret(BILLING_VAULT_KEY, "monobank_hold_enabled") or "false").lower() == "true"
        result["monobank"].update({
            "standard_enabled": monobank_standard,
            "subscription_enabled": monobank_subscription,
            "subscription_interval": await self.vault.get_secret(BILLING_VAULT_KEY, "monobank_subscription_interval") or "1m",
            "hold_enabled": monobank_hold,
            "hold_validity_days": int(await self.vault.get_secret(BILLING_VAULT_KEY, "monobank_hold_validity_days") or "9"),
            "standard_active": result["monobank"]["enabled"] and result["monobank"]["configured"] and monobank_standard,
            "subscription_active": result["monobank"]["enabled"] and result["monobank"]["configured"] and monobank_subscription,
            "hold_active": result["monobank"]["enabled"] and result["monobank"]["configured"] and monobank_hold,
        })
        result["monobank"]["active"] = result["monobank"]["standard_active"]
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
        key = plugin_key if plugin_key in {PAID_PACKAGE_KEY, "__custom_bot__"} else PAID_PACKAGE_KEY
        if key == "__custom_bot__" and period == "custom":
            raise PaymentError("Custom days are unavailable for this subscription")
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

    async def quote_days(self, guild_id: int, days: int) -> dict:
        if not 1 <= days <= 3660:
            raise PaymentError("Days must be between 1 and 3660")
        plan = (await self.session.execute(select(BillingPluginPlan).where(BillingPluginPlan.plugin_key == PAID_PACKAGE_KEY))).scalar_one_or_none()
        if plan is None or not plan.enabled or plan.is_free or plan.monthly_price is None or plan.monthly_price <= 0:
            raise PaymentError("Paid plan is unavailable")
        tier = "yearly" if days >= 365 and plan.yearly_price else "quarterly" if days >= 90 and plan.quarterly_price else "monthly"
        tier_price = getattr(plan, f"{tier}_price")
        original = max(Decimal("0.01"), (plan.monthly_price * Decimal(days) / Decimal(30)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP))
        base = (tier_price * Decimal(days) / Decimal(PERIOD_DAYS[tier])).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
        base = max(base, Decimal("0.01"))
        discount = await BillingDiscountService(self.session).quote(guild_id, base)
        return {"days": days, "currency": "USD", "tier": tier, "original_amount": original,
                "period_discount_amount": max(Decimal("0.00"), original - base), "tenure_discount_percent": discount["tenure_percent"],
                "tenure_discount_amount": base - discount["final"], "total_amount": max(Decimal("0.01"), discount["final"])}

    async def create_checkout(self, guild_id: int, plugin_key: str, period: str, provider: str, base_url: str, owner_discord_id: int, days: int | None = None, locale: str = "en") -> dict:
        key = plugin_key if plugin_key in {PAID_PACKAGE_KEY, "__custom_bot__"} else PAID_PACKAGE_KEY
        if key == "__custom_bot__" and period == "custom":
            raise PaymentError("Custom days are unavailable for this subscription")
        if (period not in PERIOD_DAYS and period != "custom") or provider not in {"liqpay", "monobank"} or (period == "custom" and days is None) or (period != "custom" and days is not None):
            raise PaymentError("Unsupported billing period or provider")
        config = await self.provider_config()
        if not config[provider]["active"]:
            raise PaymentError("Payment provider is disabled or not configured")
        plan = (await self.session.execute(select(BillingPluginPlan).where(BillingPluginPlan.plugin_key == key))).scalar_one_or_none()
        if plan is None or not plan.enabled or plan.is_free:
            raise PaymentError("Paid plan is unavailable")
        if period == "custom":
            custom_quote = await self.quote_days(guild_id, days)
            original_amount = custom_quote["original_amount"]
            base_amount = custom_quote["total_amount"]
            discount = {"total_percent": custom_quote["tenure_discount_percent"], "card_code": None}
        else:
            original_amount = getattr(plan, f"{period}_price")
            if original_amount is None or original_amount <= 0:
                raise PaymentError("Price is not configured for this period")
            discount=await BillingDiscountService(self.session).quote(guild_id,original_amount);base_amount=discount["final"]
        if base_amount <= 0:
            payment = BillingPayment(id=uuid4(), order_reference=f"voucher-{guild_id}-{uuid4().hex}", guild_id=guild_id,
                plugin_key=key, billing_period=period, provider="voucher", owner_discord_id=owner_discord_id, purpose="subscription", amount=Decimal("0.00"), currency="USD",
                status="created", signature_verified=True, original_amount_usd=original_amount, base_amount_usd=Decimal("0.00"),
                discount_percent=discount["total_percent"], discount_code=discount["card_code"])
            self.session.add(payment); await self.session.flush()
            await self._activate(payment, str(payment.id), {"source":"voucher","confirmed":True})
            return {"provider":"voucher","order_reference":payment.order_reference,"status":"paid","discount":discount}
        charge_currency="USD";amount=base_amount
        if provider == "monobank":
            try:
                quote = await public_usd_uah_rate()
            except (httpx.HTTPError, ValueError, TypeError) as exc:
                raise PaymentError("USD/UAH rate is temporarily unavailable") from exc
            amount = _monobank_amount(base_amount, quote["rate"])
            charge_currency = "UAH"
        order = f"gc-{guild_id}-{uuid4().hex}"
        payment = BillingPayment(id=uuid4(), order_reference=order, guild_id=guild_id, plugin_key=key, owner_discord_id=owner_discord_id, purpose="subscription", access_days=days if period == "custom" else PERIOD_DAYS[period],
                                 billing_period=period, provider=provider, amount=amount, currency=charge_currency,
                                 original_amount_usd=original_amount,base_amount_usd=base_amount,discount_percent=discount["total_percent"],discount_code=discount["card_code"],quote_expires_at=datetime.now(timezone.utc)+timedelta(minutes=30))
        self.session.add(payment)
        await self.session.commit()
        product = (f"GuildConsole custom Discord bot for server {guild_id} - {payment.access_days} days"
                   if key == "__custom_bot__" else
                   f"GuildConsole software modules for Discord server {guild_id} - {payment.access_days} days")
        callback = f"{base_url}/api/v1/billing/callback/{provider}"
        result_path = "/custom-bot" if key == "__custom_bot__" else "/billing"
        result = f"{base_url}{result_path}?payment={order}&guild_id={guild_id}"
        if provider == "monobank":
            token = await self.secret("monobank_token")
            amount_minor = int((amount * 100).to_integral_exact())
            checkout_text = _monobank_checkout_text(locale, guild_id, payment.access_days)
            invoice = {
                "amount": amount_minor, "ccy": 980,
                "merchantPaymInfo": {
                    "reference": order,
                    "destination": checkout_text["destination"],
                    "comment": checkout_text["destination"],
                    "basketOrder": [{"name": checkout_text["name"], "qty": 1, "sum": amount_minor, "total": amount_minor, "unit": "шт.", "icon": f"{base_url}/assets/guildconsole-product.svg"}],
                },
                "redirectUrl": result, "webHookUrl": callback,
                "validity": 1800, "paymentType": "debit",
            }
            try:
                async with httpx.AsyncClient(timeout=20) as client:
                    response = await client.post(
                        "https://api.monobank.ua/api/merchant/invoice/create",
                        headers={"X-Token": token, "X-Cms": "GuildConsole"},
                        json=invoice,
                    )
                    response.raise_for_status()
                    created = response.json()
                if not isinstance(created, dict):
                    raise PaymentError("Invalid monobank invoice response")
                invoice_id, page_url = created.get("invoiceId"), created.get("pageUrl")
                parsed = urlparse(page_url or "")
                if not invoice_id or parsed.scheme != "https" or parsed.hostname not in MONOBANK_CHECKOUT_HOSTS:
                    raise PaymentError("Invalid monobank invoice response")
            except httpx.HTTPStatusError as exc:
                try:
                    provider_error = exc.response.json()
                except ValueError:
                    provider_error = {"message": exc.response.text[:300]}
                logger.warning(
                    "Monobank invoice rejected: order=%s status=%s response=%s",
                    order,
                    exc.response.status_code,
                    provider_error,
                )
                payment.status = "failed"
                payment.raw_status = {
                    "stage": "invoice_create",
                    "http_status": exc.response.status_code,
                    "provider_error": provider_error,
                }
                await self.session.commit()
                if exc.response.status_code == 429:
                    raise PaymentError("monobank_rate_limited") from exc
                if exc.response.status_code >= 500:
                    raise PaymentError("monobank_unavailable") from exc
                raise PaymentError("monobank_invoice_rejected") from exc
            except (httpx.HTTPError, ValueError, TypeError) as exc:
                logger.exception("Monobank invoice creation failed: order=%s", order)
                payment.status = "failed"
                payment.raw_status = {"stage": "invoice_create", "error": type(exc).__name__}
                await self.session.commit()
                raise PaymentError("monobank_unavailable") from exc
            payment.provider_payment_id = str(invoice_id)
            payment.checkout_url = page_url
            await self.session.commit()
            return {"provider": provider, "order_reference": order, "checkout_url": page_url,
                    "charge_amount": amount, "charge_currency": "UAH", "base_amount_usd": base_amount,
                    "quote_minutes": 30, "discount": discount}
        public = await self.secret("liqpay_public_key"); private = await self.secret("liqpay_private_key")
        payload = {"version":"3","public_key":public,"action":"pay","amount":_money(amount),"currency":charge_currency,
                   "description":product,"product_name":product,"product_category":"Software subscription","product_url":f"{base_url}/pricing","order_id":order,"server_url":callback,"result_url":result}
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
        days = payment.access_days or PERIOD_DAYS[payment.billing_period]
        if subscription is None:
            subscription = BillingSubscription(id=uuid4(), guild_id=payment.guild_id, plugin_key=payment.plugin_key,
                status="active", billing_period=payment.billing_period, starts_at=now, expires_at=now + timedelta(days=days),
                provider=payment.provider, external_order_id=payment.order_reference,owner_discord_id=payment.owner_discord_id,auto_renew=False)
            self.session.add(subscription)
        else:
            subscription.status = "active"; subscription.billing_period = payment.billing_period
            subscription.expires_at = max(subscription.expires_at, now) + timedelta(days=days)
            subscription.provider = payment.provider; subscription.external_order_id = payment.order_reference
            if payment.owner_discord_id: subscription.owner_discord_id=payment.owner_discord_id
            subscription.auto_renew=False
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

    async def _monobank_pubkey(self, token: str, refresh: bool = False):
        cache_key = hashlib.sha256(token.encode()).hexdigest()
        cached = _monobank_pubkeys.get(cache_key)
        if not refresh and cached and cached[1] > datetime.now(timezone.utc):
            return cached[0]
        async with httpx.AsyncClient(timeout=20) as client:
            response = await client.get("https://api.monobank.ua/api/merchant/pubkey", headers={"X-Token": token})
            response.raise_for_status()
        try:
            public_key = serialization.load_pem_public_key(base64.b64decode(response.json()["key"], validate=True))
        except (ValueError, KeyError, TypeError, binascii.Error) as exc:
            raise PaymentError("Invalid monobank public key") from exc
        if not isinstance(public_key, ec.EllipticCurvePublicKey):
            raise PaymentError("Invalid monobank public key type")
        _monobank_pubkeys[cache_key] = (public_key, datetime.now(timezone.utc) + timedelta(hours=24))
        return public_key

    async def confirm_monobank(self, body: bytes, signature: str) -> None:
        if not signature:
            raise PaymentError("Missing monobank signature")
        token = await self.secret("monobank_token")
        try:
            signature_bytes = base64.b64decode(signature, validate=True)
        except (ValueError, TypeError, binascii.Error) as exc:
            raise PaymentError("Invalid monobank signature") from exc
        for refresh in (False, True):
            key = await self._monobank_pubkey(token, refresh=refresh)
            try:
                key.verify(signature_bytes, body, ec.ECDSA(hashes.SHA256()))
                break
            except (InvalidSignature, ValueError):
                if refresh:
                    raise PaymentError("Invalid monobank signature")
        try:
            notification = json.loads(body)
        except (ValueError, TypeError) as exc:
            raise PaymentError("Invalid monobank webhook body") from exc
        if not isinstance(notification, dict):
            raise PaymentError("Invalid monobank webhook body")
        invoice_id = str(notification.get("invoiceId") or "")
        if not invoice_id:
            raise PaymentError("Missing monobank invoice ID")
        payment = (await self.session.execute(select(BillingPayment).where(
            BillingPayment.provider == "monobank", BillingPayment.provider_payment_id == invoice_id,
        ).with_for_update())).scalar_one_or_none()
        if payment is None:
            raise PaymentError("Unknown monobank invoice")
        if payment.status == "paid":
            return
        return await self.refresh_monobank(payment, notification.get("status"))

    async def refresh_monobank(self, payment: BillingPayment, notified_status: str | None = None) -> str:
        if payment.provider != "monobank" or not payment.provider_payment_id:
            raise PaymentError("Unknown monobank invoice")
        if payment.status == "paid":
            return "paid"
        token = await self.secret("monobank_token")
        invoice_id = payment.provider_payment_id
        async with httpx.AsyncClient(timeout=20) as client:
            response = await client.get("https://api.monobank.ua/api/merchant/invoice/status", headers={"X-Token": token}, params={"invoiceId": invoice_id})
            response.raise_for_status()
            verified = response.json()
        if not isinstance(verified, dict):
            raise PaymentError("Invalid monobank status response")
        if _monobank_confirmed(verified, payment):
            await self._activate(payment, invoice_id, verified)
            return "paid"
        provider_status = str(verified.get("status") or "")
        if provider_status in {"failure", "expired", "reversed"}:
            payment.status = "failed"
            payment.raw_status = verified
            await self.session.commit()
            return "failed"
        if provider_status in {"created", "processing", "hold"}:
            if notified_status == "success":
                raise PaymentVerificationPending("Bank status is still updating")
            return "pending"
        raise PaymentError("Monobank invoice status does not match the order")
