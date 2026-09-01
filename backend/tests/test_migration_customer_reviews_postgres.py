import os
import uuid
from pathlib import Path

import pytest
import sqlalchemy as sa
from alembic import command
from alembic.config import Config
from sqlalchemy.ext.asyncio import AsyncConnection, create_async_engine
from sqlalchemy.pool import NullPool

from app.core.config import get_settings

PREVIOUS_REVISION = "c6c7c3026e63"
REVIEW_REVISION = "d4a9e7c31f26"


def _alembic_config(connection: sa.Connection) -> Config:
    config = Config(str(Path(__file__).parents[1] / "alembic.ini"))
    config.attributes["connection"] = connection
    return config


async def _upgrade(connection: AsyncConnection, revision: str) -> None:
    await connection.run_sync(
        lambda sync_connection: command.upgrade(_alembic_config(sync_connection), revision)
    )
    await connection.commit()


async def _revision(connection: AsyncConnection, schema: str) -> str | None:
    version_table = sa.table("alembic_version", sa.column("version_num"), schema=schema)
    return await connection.scalar(sa.select(version_table.c.version_num))


def test_review_migration_is_a_new_child_of_current_head() -> None:
    source = (
        Path(__file__).parents[1]
        / "migrations/versions/d4a9e7c31f26_add_verified_customer_reviews.py"
    ).read_text(encoding="utf-8")
    assert f'"{PREVIOUS_REVISION}"' in source
    assert "uq_customer_reviews_booking" in source
    assert "rating BETWEEN 1 AND 5" in source
    assert "next_prompt_after BETWEEN 1 AND 3" in source
    assert "guest_device_id_hash" in source
    assert "review_token" not in source


@pytest.mark.asyncio
@pytest.mark.postgres
@pytest.mark.skipif(
    os.getenv("RUN_POSTGRES_MIGRATION_TESTS") != "1",
    reason="Set RUN_POSTGRES_MIGRATION_TESTS=1 for isolated-schema PostgreSQL migration tests.",
)
async def test_review_migration_upgrades_real_postgres_with_constraints() -> None:
    schema = f"test_reviews_{uuid.uuid4().hex}"
    engine = create_async_engine(get_settings().database_url, poolclass=NullPool)
    try:
        async with engine.connect() as connection:
            await connection.execute(sa.text(f'CREATE SCHEMA "{schema}"'))
            await connection.commit()
            await connection.execute(sa.text(f'SET search_path TO "{schema}"'))
            await _upgrade(connection, PREVIOUS_REVISION)
            assert await _revision(connection, schema) == PREVIOUS_REVISION

            await _upgrade(connection, REVIEW_REVISION)
            assert await _revision(connection, schema) == REVIEW_REVISION
            tables = set(
                (
                    await connection.execute(
                        sa.text(
                            "SELECT table_name FROM information_schema.tables "
                            "WHERE table_schema=:schema"
                        ),
                        {"schema": schema},
                    )
                ).scalars()
            )
            assert {
                "customer_reviews",
                "customer_review_prompt_states",
                "guest_review_verification_attempts",
                "deleted_customer_identities",
            } <= tables
            constraints = set(
                (
                    await connection.execute(
                        sa.text(
                            "SELECT c.conname FROM pg_constraint c "
                            "JOIN pg_class t ON t.oid=c.conrelid "
                            "JOIN pg_namespace n ON n.oid=t.relnamespace "
                            "WHERE n.nspname=:schema AND t.relname IN "
                            "('customer_reviews','customer_review_prompt_states')"
                        ),
                        {"schema": schema},
                    )
                ).scalars()
            )
            assert "uq_customer_reviews_booking" in constraints
            assert any("customer_review_rating" in name for name in constraints)
            assert any("review_prompt_threshold" in name for name in constraints)
    finally:
        async with engine.begin() as cleanup:
            assert schema.startswith("test_reviews_")
            await cleanup.execute(sa.text(f'DROP SCHEMA IF EXISTS "{schema}" CASCADE'))
        await engine.dispose()
