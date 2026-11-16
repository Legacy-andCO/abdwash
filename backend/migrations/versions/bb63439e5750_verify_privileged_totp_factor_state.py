"""verify privileged TOTP factor state

Revision ID: bb63439e5750
Revises: c7e833583da3
Create Date: 2026-11-11 17:02:05.407462
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "bb63439e5750"
down_revision: str | None = "c7e833583da3"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute("""DO $setup$ BEGIN
      IF to_regclass('auth.mfa_factors') IS NOT NULL THEN
        EXECUTE $ddl$ CREATE FUNCTION app_private.privileged_totp_active(session_id uuid,user_id uuid)
        RETURNS boolean LANGUAGE sql STABLE SECURITY DEFINER SET search_path='' AS $body$
          SELECT EXISTS(SELECT 1 FROM auth.sessions s JOIN auth.mfa_factors f ON f.id=s.factor_id
            WHERE s.id=$1 AND s.user_id=$2 AND f.user_id=$2
              AND f.factor_type::text='totp' AND f.status::text='verified')
        $body$ $ddl$;
        REVOKE ALL ON FUNCTION app_private.privileged_totp_active(uuid,uuid) FROM PUBLIC;
        GRANT EXECUTE ON FUNCTION app_private.privileged_totp_active(uuid,uuid) TO trifecta_runtime;
      END IF;
    END $setup$""")


def downgrade() -> None:
    op.execute("DROP FUNCTION IF EXISTS app_private.privileged_totp_active(uuid,uuid)")
