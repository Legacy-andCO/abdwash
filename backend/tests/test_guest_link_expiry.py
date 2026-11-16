import uuid
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from app.domain.errors import DomainError
from app.services.booking_management import load_managed_booking
from app.services.management_tokens import create_management_token, management_token_hash


async def test_guest_links_expire_without_losing_authenticated_history():
    booking_id = uuid.uuid4()
    token = create_management_token(booking_id)
    record = SimpleNamespace(
        management_token_hash=management_token_hash(token),
        scheduled_end=datetime.now(UTC) - timedelta(days=31),
    )
    db = AsyncMock()
    db.scalars.return_value.one_or_none = lambda: record
    with pytest.raises(DomainError) as e:
        await load_managed_booking(db, token)
    assert e.value.status_code == 410
    record.scheduled_end = datetime.now(UTC)
    assert await load_managed_booking(db, token) is record
    record.management_token_hash = "0" * 64
    with pytest.raises(DomainError) as e:
        await load_managed_booking(db, token)
    assert e.value.status_code == 404
