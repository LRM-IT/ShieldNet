import base64
import hashlib
import hmac
import json
import time
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from uuid import uuid4

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.billing import BillingPayment, BillingPluginPlan, BillingSubscription, BillingWallet, BillingWalletTransaction
from app.services.billing_service import PAID_PACKAGE_KEY, normalize_plugin_key
from app.services.plugin_control_service import PluginControlService
from app.services.nbu_exchange import NBUExchangeService, ExchangeRateError, SUPPORTED_DISPLAY_CURRENCIES
from app.services.billing_discounts import BillingDiscountService


BILLING_VAULT_KEY = "core_billing"
PERIOD_DAYS = {"monthly": 30, "quarterly": 90, "yearly": 365}
PROVIDER_CURRENCIES = {"wayforpay":{"UAH","USD","EUR"}, "liqpay":{"UAH","USD","EUR"}}


class PaymentError(ValueError):
    pass


def _money(value: Decimal) -> str:
    return f"{value:.2f}"


def _wfp_signature(secret: str, values: list[object]) -> str:
    return hmac.new(secret.encode(), ";".join(str(v) for v in values).encode(), hashlib.md5).hexdigest()


def _liqpay_signature(private_key: str, data: str) -> str:
    digest = hashlib.sha1(f"{private_key}{data}{private_key}".encode()).digest()
    return base64.b64encode(digest).decode()


class BillingPaymentService:
    def __init__(self, session: AsyncSession):
        self.session = session
        self.vault = PluginControlService(session)

    async def provider_config(self) -> dict:
        names = {x.secret_name for x in await self.vault.list_secrets(BILLING_VAULT_KEY)}
        wfp_enabled = (await self.vault.get_secret(BILLING_VAULT_KEY, "wfp_enabled") or "true").lower() == "true"
        liqpay_enabled = (await self.vault.get_secret(BILLING_VAULT_KEY, "liqpay_enabled") or "true").lower() == "true"
        wfp_configured = {"wfp_merchant_account", "wfp_secret_key", "wfp_merchant_domain"} <= names
        liqpay_configured = {"liqpay_public_key", "liqpay_private_key"} <= names
        return {
            "wayforpay": {
                "enabled": wfp_enabled,
                "configured": wfp_configured,
                "active": wfp_enabled and wfp_configured,
                "merchant_account": await self.vault.get_secret(BILLING_VAULT_KEY, "wfp_merchant_account") or "",
                "merchant_domain": await self.vault.get_secret(BILLING_VAULT_KEY, "wfp_merchant_domain") or "",
                "secret_saved": "wfp_secret_key" in names,
            },
            "liqpay": {
                "enabled": liqpay_enabled,
                "configured": liqpay_configured,
                "active": liqpay_enabled and liqpay_configured,
                "public_key": await self.vault.get_secret(BILLING_VAULT_KEY, "liqpay_public_key") or "",
                "secret_saved": "liqpay_private_key" in names,
            },
        }

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

    async def create_wallet_topup(self, discord_user_id:int, display_amount:Decimal, provider:str, base_url:str, display_currency:str="USD") -> dict:
        config=await self.provider_config()
        if provider not in config or not config[provider]["active"]: raise PaymentError("Payment provider is disabled or not configured")
        currency=display_currency.upper()
        if currency not in SUPPORTED_DISPLAY_CURRENCIES:
            raise PaymentError("Unsupported display currency")
        if currency not in PROVIDER_CURRENCIES[provider]:
            raise PaymentError(f"{provider} does not support payments in {currency}; select UAH, USD or EUR in your profile")
        charge_currency=currency
        amount=display_amount
        amount_usd,rate=await NBUExchangeService(self.session).convert_to_usd(display_amount,currency)
        order=f"wallet-{discord_user_id}-{uuid4().hex}"
        payment=BillingPayment(id=uuid4(),order_reference=order,guild_id=None,plugin_key=None,billing_period=None,purpose="wallet_topup",owner_discord_id=discord_user_id,provider=provider,amount=amount,currency=charge_currency,base_amount_usd=amount_usd,original_amount_usd=amount_usd,fx_rate=rate,quote_expires_at=datetime.now(timezone.utc)+timedelta(minutes=30))
        self.session.add(payment);await self.session.commit()
        product="GuildConsole balance top-up";callback=f"{base_url}/api/v1/billing/callback/{provider}";result=f"{base_url}/servers"
        if provider=="wayforpay":
            merchant=await self.secret("wfp_merchant_account");secret=await self.secret("wfp_secret_key");domain=await self.secret("wfp_merchant_domain");created=int(time.time())
            values=[merchant,domain,order,created,_money(amount),charge_currency,product,"1",_money(amount)]
            fields={"merchantAccount":merchant,"merchantAuthType":"SimpleSignature","merchantDomainName":domain,"orderReference":order,"orderDate":created,"amount":_money(amount),"currency":charge_currency,"productName":[product],"productPrice":[_money(amount)],"productCount":["1"],"merchantSignature":_wfp_signature(secret,values),"serviceUrl":callback,"returnUrl":result}
            return {"provider":provider,"action":"https://secure.wayforpay.com/pay","fields":fields,"charge_amount":amount,"charge_currency":charge_currency}
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

    async def create_checkout(self, guild_id: int, plugin_key: str, period: str, provider: str, base_url: str, display_currency: str = "USD") -> dict:
        key = PAID_PACKAGE_KEY
        if period not in PERIOD_DAYS or provider not in {"wayforpay", "liqpay"}:
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
        requested_currency = display_currency.upper()
        if requested_currency not in SUPPORTED_DISPLAY_CURRENCIES:
            requested_currency = "USD"
        try:
            display_amount = await NBUExchangeService(self.session).convert_from_usd(base_amount, requested_currency)
        except ExchangeRateError as exc:
            raise PaymentError(str(exc)) from exc
        if requested_currency not in PROVIDER_CURRENCIES[provider]:
            raise PaymentError(f"{provider} does not support payments in {requested_currency}; select UAH, USD or EUR in your profile")
        charge_currency = requested_currency
        amount = display_amount
        _, fx_rate = await NBUExchangeService(self.session).convert_to_usd(Decimal("1"), charge_currency)
        order = f"gc-{guild_id}-{uuid4().hex}"
        payment = BillingPayment(id=uuid4(), order_reference=order, guild_id=guild_id, plugin_key=key,
                                 billing_period=period, provider=provider, amount=amount, currency=charge_currency,
                                 original_amount_usd=original_amount,base_amount_usd=base_amount,discount_percent=discount["total_percent"],discount_code=discount["card_code"],fx_rate=fx_rate, quote_expires_at=datetime.now(timezone.utc)+timedelta(minutes=30))
        self.session.add(payment)
        await self.session.commit()
        product = f"GuildConsole Paid Modules {period}"
        callback = f"{base_url}/api/v1/billing/callback/{provider}"
        result = f"{base_url}/guild/{guild_id}/billing"
        if provider == "wayforpay":
            merchant = await self.secret("wfp_merchant_account"); secret = await self.secret("wfp_secret_key")
            domain = await self.secret("wfp_merchant_domain"); created = int(time.time())
            values = [merchant, domain, order, created, _money(amount), charge_currency, product, "1", _money(amount)]
            fields = {"merchantAccount":merchant,"merchantAuthType":"SimpleSignature","merchantDomainName":domain,
                      "orderReference":order,"orderDate":created,"amount":_money(amount),"currency":charge_currency,
                      "productName":[product],"productPrice":[_money(amount)],"productCount":["1"],
                      "merchantSignature":_wfp_signature(secret, values),"serviceUrl":callback,"returnUrl":result}
            return {"provider":provider,"order_reference":order,"action":"https://secure.wayforpay.com/pay","method":"POST","fields":fields,
                    "charge_amount":amount,"charge_currency":charge_currency,"display_amount":display_amount,"display_currency":requested_currency,"quote_minutes":30,"discount":discount}
        public = await self.secret("liqpay_public_key"); private = await self.secret("liqpay_private_key")
        payload = {"version":"3","public_key":public,"action":"pay","amount":_money(amount),"currency":charge_currency,
                   "description":product,"order_id":order,"server_url":callback,"result_url":result}
        data = base64.b64encode(json.dumps(payload, separators=(",", ":")).encode()).decode()
        return {"provider":provider,"order_reference":order,"action":"https://www.liqpay.ua/api/3/checkout","method":"POST",
                "fields":{"data":data,"signature":_liqpay_signature(private, data)},"charge_amount":amount,"charge_currency":charge_currency,
                "display_amount":display_amount,"display_currency":requested_currency,"quote_minutes":30,"discount":discount}

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

    async def confirm_wayforpay(self, payload: dict) -> dict:
        order = str(payload.get("orderReference", ""))
        payment = (await self.session.execute(select(BillingPayment).where(BillingPayment.order_reference == order).with_for_update())).scalar_one_or_none()
        if payment is None or payment.provider != "wayforpay":
            raise PaymentError("Unknown payment")
        secret = await self.secret("wfp_secret_key"); merchant = await self.secret("wfp_merchant_account")
        callback_sig = _wfp_signature(secret, [payload.get(k, "") for k in ("merchantAccount","orderReference","amount","currency","authCode","cardPan","transactionStatus","reasonCode")])
        if not hmac.compare_digest(callback_sig, str(payload.get("merchantSignature", ""))):
            raise PaymentError("Invalid WayForPay signature")
        check = {"transactionType":"CHECK_STATUS","merchantAccount":merchant,"orderReference":order}
        check["merchantSignature"] = _wfp_signature(secret, [merchant, order])
        async with httpx.AsyncClient(timeout=20) as client:
            response = await client.post("https://api.wayforpay.com/api", json=check); response.raise_for_status(); verified = response.json()
        if verified.get("transactionStatus") != "Approved" or Decimal(str(verified.get("amount", 0))) != payment.amount or verified.get("currency") != payment.currency:
            payment.status = "rejected"; payment.raw_status = verified; await self.session.commit()
            raise PaymentError("WayForPay did not confirm the payment")
        await self._complete(payment, str(verified.get("authCode") or ""), verified)
        stamp = int(time.time())
        return {"orderReference":order,"status":"accept","time":stamp,"signature":_wfp_signature(secret,[order,"accept",stamp])}

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
