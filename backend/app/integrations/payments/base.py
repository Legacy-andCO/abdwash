from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True)
class ProviderPayment:
    provider_payment_id: str
    status: str


class PaymentProvider(Protocol):
    async def create_payment(
        self, *, amount_minor: int, currency_code: str, idempotency_key: str
    ) -> ProviderPayment: ...

    async def query_payment(self, provider_payment_id: str) -> ProviderPayment: ...

    async def refund_payment(
        self, *, provider_payment_id: str, amount_minor: int, idempotency_key: str
    ) -> ProviderPayment: ...
