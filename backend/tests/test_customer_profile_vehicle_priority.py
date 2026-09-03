import uuid
from unittest.mock import AsyncMock, MagicMock

import pytest
from sqlalchemy.dialects import postgresql
from sqlalchemy.ext.asyncio import AsyncSession

from app.services.customer_profiles import load_saved_customer_details


@pytest.mark.asyncio
async def test_saved_vehicles_are_ranked_by_completed_use_then_recency() -> None:
    result = MagicMock()
    result.mappings.return_value = []
    session = MagicMock(spec=AsyncSession)
    session.execute = AsyncMock(return_value=result)

    await load_saved_customer_details(session, uuid.uuid4())

    statement = session.execute.await_args.args[0]
    sql = str(
        statement.compile(
            dialect=postgresql.dialect(),
            compile_kwargs={"literal_binds": True},
        )
    ).lower()
    assert "count(booking_vehicles.id)" in sql
    assert "bookings.status = 'completed'" in sql
    assert "usage_count desc" in sql
    assert "last_used_at desc nulls last" in sql
    assert "created_at desc" in sql
