import importlib.util
import os
import uuid
from pathlib import Path
from types import ModuleType

import pytest
import sqlalchemy as sa
from alembic import command
from alembic.config import Config
from sqlalchemy.dialects.postgresql import asyncpg
from sqlalchemy.ext.asyncio import AsyncConnection, create_async_engine
from sqlalchemy.pool import NullPool

from app.core.config import get_settings

MIGRATION_PATH = (
    Path(__file__).parents[1]
    / "migrations/versions/c18f4a7b2d91_add_catalogue_invoicing_and_expense_evidence.py"
)
APPROVED_PRICES = {
    "Standard Wash": (7_300, 8_600),
    "Gold Wash": (9_300, 10_500),
    "Premium Wash": (12_500, 13_500),
    "Monthly Package": (26_000, 37_000),
    "Interior Deep Cleaning": (35_000, 42_000),
    "Exterior Polishing": (40_000, 52_000),
}
CAR_TYPES = {"sedan", "hatchback", "coupe", "other"}
SUV_TYPES = {"suv", "pickup", "van"}


def _migration_module() -> ModuleType:
    spec = importlib.util.spec_from_file_location("migration_c18", MIGRATION_PATH)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_c18_catalogue_statements_have_explicit_asyncpg_bind_types() -> None:
    migration = _migration_module()
    statements = (
        migration._service_insert_statement(),
        migration._service_update_statement(),
        migration._service_price_upsert_statement(),
    )
    compiled = "\n".join(
        str(statement.compile(dialect=asyncpg.dialect())) for statement in statements
    )
    assert "::VARCHAR" in compiled
    assert "::INTEGER" in compiled
    assert "::JSON" in compiled
    assert "::BOOLEAN" in compiled
    assert "CAST($" not in compiled
    for statement in statements:
        assert all(
            not isinstance(bind.type, sa.types.NullType) for bind in statement._bindparams.values()
        )


def _alembic_config(connection: sa.Connection) -> Config:
    config = Config(str(Path(__file__).parents[1] / "alembic.ini"))
    config.attributes["connection"] = connection
    return config


async def _run_revision(connection: AsyncConnection, revision: str) -> None:
    await connection.run_sync(
        lambda sync_connection: command.upgrade(_alembic_config(sync_connection), revision)
    )
    await connection.commit()


async def _public_migration_state(connection: AsyncConnection) -> tuple[str | None, bool]:
    return (
        await connection.scalar(sa.text("SELECT version_num FROM public.alembic_version")),
        bool(
            await connection.scalar(
                sa.text(
                    "SELECT EXISTS (SELECT 1 FROM information_schema.columns "
                    "WHERE table_schema='public' AND table_name='services' "
                    "AND column_name='included_features')"
                )
            )
        ),
    )


async def _schema_version(connection: AsyncConnection, schema: str) -> str | None:
    version_table = sa.table("alembic_version", sa.column("version_num"), schema=schema)
    return await connection.scalar(sa.select(version_table.c.version_num))


@pytest.mark.asyncio
@pytest.mark.skipif(
    os.getenv("RUN_POSTGRES_MIGRATION_TESTS") != "1",
    reason="Set RUN_POSTGRES_MIGRATION_TESTS=1 for isolated-schema PostgreSQL migration tests.",
)
async def test_c18_upgrades_real_postgres_without_duplicate_catalogue_rows() -> None:
    schema = f"test_c18_{uuid.uuid4().hex}"
    assert schema.startswith("test_c18_") and len(schema) == 41
    engine = create_async_engine(get_settings().database_url, poolclass=NullPool)
    business_id = uuid.uuid4()
    public_state: tuple[str | None, bool] | None = None
    try:
        async with engine.connect() as connection:
            public_state = await _public_migration_state(connection)
            await connection.execute(sa.text(f'CREATE SCHEMA "{schema}"'))
            await connection.commit()
            # Keep public out of the path. Falling through to public would make Alembic
            # see the real version table and could apply this test migration there.
            await connection.execute(sa.text(f'SET search_path TO "{schema}"'))
            await _run_revision(connection, "8a72c1d4e6f0")
            assert await connection.scalar(
                sa.text("SELECT to_regclass('businesses') IS NOT NULL")
            )
            assert await _schema_version(connection, schema) == "8a72c1d4e6f0"
            await connection.execute(
                sa.text(
                    "INSERT INTO businesses (id,name,slug,is_active) "
                    "VALUES (:id,'Migration Test','migration-test',true)"
                ).bindparams(sa.bindparam("id", type_=sa.Uuid())),
                {"id": business_id},
            )
            await connection.execute(
                sa.text(
                    "INSERT INTO services "
                    "(id,business_id,name,description,price_minor,"
                    "estimated_duration_minutes,is_active,mobile_available,"
                    "shop_available,sort_order) VALUES "
                    "(gen_random_uuid(),:business_id,'Development Standard Wash',"
                    "'obsolete',100,60,true,true,true,0)"
                ).bindparams(sa.bindparam("business_id", type_=sa.Uuid())),
                {"business_id": business_id},
            )
            await connection.commit()

            await _run_revision(connection, "c18f4a7b2d91")
            assert await _schema_version(connection, schema) == "c18f4a7b2d91"
            rows = (
                await connection.execute(
                    sa.text(
                        "SELECT s.name,s.product_kind,s.customer_bookable,sp.vehicle_type,"
                        "sp.price_minor FROM services s JOIN service_prices sp "
                        "ON sp.service_id=s.id WHERE s.business_id=:business_id "
                        "AND s.name = ANY(:names) ORDER BY s.name,sp.vehicle_type"
                    ).bindparams(
                        sa.bindparam("business_id", type_=sa.Uuid()),
                        sa.bindparam("names", type_=sa.ARRAY(sa.String(160))),
                    ),
                    {"business_id": business_id, "names": list(APPROVED_PRICES)},
                )
            ).all()
            _assert_catalogue(rows)
            assert (
                await connection.scalar(
                    sa.text(
                        "SELECT is_active FROM services WHERE business_id=:business_id "
                        "AND name='Development Standard Wash'"
                    ).bindparams(sa.bindparam("business_id", type_=sa.Uuid())),
                    {"business_id": business_id},
                )
                is False
            )

            await connection.run_sync(
                lambda sync_connection: command.downgrade(
                    _alembic_config(sync_connection), "8a72c1d4e6f0"
                )
            )
            await connection.commit()
            await _run_revision(connection, "c18f4a7b2d91")
            rerun_rows = (
                await connection.execute(
                    sa.text(
                        "SELECT s.name,s.product_kind,s.customer_bookable,sp.vehicle_type,"
                        "sp.price_minor FROM services s JOIN service_prices sp "
                        "ON sp.service_id=s.id WHERE s.business_id=:business_id "
                        "AND s.name = ANY(:names) ORDER BY s.name,sp.vehicle_type"
                    ).bindparams(
                        sa.bindparam("business_id", type_=sa.Uuid()),
                        sa.bindparam("names", type_=sa.ARRAY(sa.String(160))),
                    ),
                    {"business_id": business_id, "names": list(APPROVED_PRICES)},
                )
            ).all()
            _assert_catalogue(rerun_rows)
            assert await _schema_version(connection, schema) == "c18f4a7b2d91"
    finally:
        async with engine.connect() as cleanup:
            await cleanup.execute(sa.text(f'DROP SCHEMA IF EXISTS "{schema}" CASCADE'))
            await cleanup.commit()
            if public_state is not None:
                assert await _public_migration_state(cleanup) == public_state
        await engine.dispose()


def _assert_catalogue(rows: list[sa.Row[tuple[str, str, bool, str, int]]]) -> None:
    by_service: dict[str, list[tuple[str, int]]] = {}
    metadata: dict[str, tuple[str, bool]] = {}
    for name, product_kind, customer_bookable, vehicle_type, price_minor in rows:
        by_service.setdefault(name, []).append((vehicle_type, price_minor))
        metadata[name] = (product_kind, customer_bookable)
    assert set(by_service) == set(APPROVED_PRICES)
    for name, (car_price, suv_price) in APPROVED_PRICES.items():
        prices = dict(by_service[name])
        assert len(prices) == 7
        assert {vehicle_type for vehicle_type, price in prices.items() if price == car_price} == (
            CAR_TYPES
        )
        assert {vehicle_type for vehicle_type, price in prices.items() if price == suv_price} == (
            SUV_TYPES
        )
    assert metadata["Monthly Package"] == ("monthly_package", False)
    assert all(
        metadata[name] == ("single_service", True)
        for name in APPROVED_PRICES
        if name != "Monthly Package"
    )
