"""Read-only target verification; deliberately never prints the configured URL."""

import asyncio

from sqlalchemy import text

from app.core.config import get_settings
from app.core.database import create_engine


async def inspect() -> None:
    engine = create_engine(get_settings())
    try:
        async with engine.connect() as connection:
            row = (
                await connection.execute(
                    text(
                        "select current_database(), current_user, inet_server_addr()::text, "
                        "(select count(*) from information_schema.tables "
                        "where table_schema='public' and table_type='BASE TABLE')"
                    )
                )
            ).one()
            print(
                {
                    "database": row[0],
                    "user": row[1],
                    "server_address_present": bool(row[2]),
                    "public_table_count": row[3],
                }
            )
    finally:
        await engine.dispose()


if __name__ == "__main__":
    asyncio.run(inspect())
