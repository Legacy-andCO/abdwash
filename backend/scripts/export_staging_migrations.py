"""Render the real Alembic upgrades for connector-only staging bootstrap.

Does not connect to a database. SQL is for a NEW, EMPTY isolated database only.
Each revision preserves its predecessor check and version checkpoint; this is
not a schema snapshot or an Alembic stamp. JSON values are encoded as SQL text
literals because SQLAlchemy's JSON type has no offline literal renderer.
"""

import hashlib
import json
from pathlib import Path

import sqlalchemy as sa
from alembic.migration import MigrationContext
from alembic.operations import Operations
from alembic.script import ScriptDirectory
from sqlalchemy.sql.elements import TextClause

from app.models import Base


def export() -> list[dict[str, str]]:
    statements: list[str] = []
    engine = None

    def emit(statement, *multiparams, **kwargs):
        if isinstance(statement, str):
            statement = sa.text(statement)
        values = multiparams[0] if multiparams and multiparams[0] else {}
        if values:
            if not isinstance(statement, TextClause):
                raise ValueError("Review unsupported parameterized migration statement")
            statement = statement.params(**values)
            for key, bind in list(statement._bindparams.items()):
                if isinstance(bind.type, sa.JSON):
                    statement = statement.bindparams(
                        sa.bindparam(key, json.dumps(bind.value), type_=sa.Text())
                    )
        statements.append(
            str(statement.compile(dialect=engine.dialect, compile_kwargs={"literal_binds": True}))
            .strip()
            .rstrip(";")
            + ";"
        )

    # Connector SQL is sent verbatim, without DBAPI percent interpolation.
    engine = sa.create_mock_engine("postgresql://", emit, paramstyle="named")
    context = MigrationContext.configure(engine, opts={"target_metadata": Base.metadata})
    script = ScriptDirectory("migrations")
    result = []
    for revision in reversed(list(script.walk_revisions())):
        statements.clear()
        if revision.down_revision is None:
            statements.append(
                "CREATE TABLE public.alembic_version (version_num varchar(32) PRIMARY KEY);"
            )
            statements.append(
                "DO $$ BEGIN IF EXISTS(SELECT FROM public.alembic_version) THEN RAISE EXCEPTION 'Expected empty Alembic state'; END IF; END $$;"
            )
        else:
            statements.append(
                f"DO $$ BEGIN IF (SELECT version_num FROM public.alembic_version) IS DISTINCT FROM '{revision.down_revision}' THEN RAISE EXCEPTION 'Unexpected Alembic predecessor'; END IF; END $$;"
            )
        with Operations.context(context):
            revision.module.upgrade()
        if revision.down_revision is None:
            statements.append(f"INSERT INTO public.alembic_version VALUES ('{revision.revision}');")
        else:
            statements.append(
                f"UPDATE public.alembic_version SET version_num='{revision.revision}' WHERE version_num='{revision.down_revision}';"
            )
        sql = "\n".join(statements)
        result.append(
            {
                "revision": revision.revision,
                "sql": sql,
                "sha256": hashlib.sha256(sql.encode()).hexdigest(),
            }
        )
    return result


if __name__ == "__main__":
    target = Path("../tmp/staging-migrations.json")
    target.parent.mkdir(exist_ok=True, parents=True)
    rendered = export()
    target.write_text(json.dumps(rendered), encoding="utf-8")
    print(json.dumps({"revisions": len(rendered), "head": rendered[-1]["revision"]}))
