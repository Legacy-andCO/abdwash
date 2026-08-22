from app.integrations.payments.base import ProviderPayment


class FakePaymentProvider:
    """Deterministic test adapter; never configured as a production gateway."""

    async def create_payment(
        self, *, amount_minor: int, currency_code: str, idempotency_key: str
    ) -> ProviderPayment:
        return ProviderPayment(provider_payment_id=f"fake-{idempotency_key}", status="pending")

    async def query_payment(self, provider_payment_id: str) -> ProviderPayment:
        return ProviderPayment(provider_payment_id=provider_payment_id, status="pending")

    async def refund_payment(
        self, *, provider_payment_id: str, amount_minor: int, idempotency_key: str
    ) -> ProviderPayment:
        return ProviderPayment(provider_payment_id=provider_payment_id, status="refunded")
