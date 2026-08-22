import pytest

from app.integrations.payments.fake import FakePaymentProvider


@pytest.mark.asyncio
async def test_fake_payment_provider_never_reports_paid() -> None:
    provider = FakePaymentProvider()
    result = await provider.create_payment(
        amount_minor=10000, currency_code="AED", idempotency_key="test-key"
    )
    assert result.status == "pending"
