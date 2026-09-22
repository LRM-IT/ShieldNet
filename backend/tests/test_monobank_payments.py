import base64
import json
import unittest
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import ec

from app.services.billing_payments import (
    BillingPaymentService, PaymentError, _monobank_amount, _monobank_confirmed,
)


class _Rows:
    def __init__(self, payment):
        self.payment = payment

    def scalar_one_or_none(self):
        return self.payment


class _Session:
    def __init__(self, payment):
        self.payment = payment

    async def execute(self, _query):
        return _Rows(self.payment)


class MonobankPaymentTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.payment = SimpleNamespace(
            provider_payment_id="p2_test", order_reference="gc-test",
            amount=Decimal("135.00"), status="created", currency="UAH", provider="monobank",
        )

    def test_conversion_and_order_matching(self):
        self.assertEqual(_monobank_amount(Decimal("3.00"), 45.0005), Decimal("135.00"))
        status = {"status": "success", "invoiceId": "p2_test", "reference": "gc-test", "ccy": 980, "amount": 13500}
        self.assertTrue(_monobank_confirmed(status, self.payment))
        for changed in ({"amount": 13501}, {"ccy": 840}, {"reference": "other"}, {"invoiceId": "other"}, {"status": "processing"}):
            self.assertFalse(_monobank_confirmed({**status, **changed}, self.payment))

    async def test_signed_webhook_requires_matching_bank_status(self):
        key = ec.generate_private_key(ec.SECP256R1())
        body = json.dumps({"invoiceId": "p2_test"}).encode()
        signature = base64.b64encode(key.sign(body, ec.ECDSA(hashes.SHA256()))).decode()
        service = BillingPaymentService(_Session(self.payment))
        service.secret = AsyncMock(return_value="test-token")
        service._monobank_pubkey = AsyncMock(return_value=key.public_key())
        service._activate = AsyncMock()
        status = {"status": "success", "invoiceId": "p2_test", "reference": "gc-test", "ccy": 980, "amount": 13500}
        response = SimpleNamespace(raise_for_status=lambda: None, json=lambda: status)
        client = SimpleNamespace(get=AsyncMock(return_value=response))
        context = AsyncMock()
        context.__aenter__.return_value = client
        with patch("app.services.billing_payments.httpx.AsyncClient", return_value=context):
            await service.confirm_monobank(body, signature)
            service._activate.assert_awaited_once()
            service._activate.reset_mock()
            with self.assertRaises(PaymentError):
                await service.confirm_monobank(body, base64.b64encode(b"invalid").decode())
            service._activate.assert_not_awaited()
            status["amount"] = 13501
            with self.assertRaises(PaymentError):
                await service.confirm_monobank(body, signature)
            service._activate.assert_not_awaited()


if __name__ == "__main__":
    unittest.main()
