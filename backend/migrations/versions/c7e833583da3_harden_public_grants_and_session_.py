"""harden public grants and session boundaries

Revision ID: c7e833583da3
Revises: a83b97c41d62
Create Date: 2026-11-11 14:52:16.162126
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "c7e833583da3"
down_revision: str | None = "a83b97c41d62"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "api_rate_windows",
        sa.Column("scope", sa.String(100), primary_key=True),
        sa.Column("window_start", sa.DateTime(timezone=True), primary_key=True),
        sa.Column("attempts", sa.Integer(), nullable=False),
    )
    op.create_index("ix_api_rate_windows_expiry", "api_rate_windows", ["window_start"])
    # FastAPI is the sole business API. Do not invent direct-client ownership policies.
    op.execute("""
    DO $hardening$
    DECLARE item record; client_role text;
    BEGIN
      IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'trifecta_runtime') THEN
        CREATE ROLE trifecta_runtime NOLOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOBYPASSRLS;
      END IF;
      GRANT USAGE ON SCHEMA public TO trifecta_runtime;
      FOR item IN SELECT c.relname FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace
                  WHERE n.nspname='public' AND c.relkind IN ('r','p') LOOP
        EXECUTE format('ALTER TABLE public.%I ENABLE ROW LEVEL SECURITY', item.relname);
        EXECUTE format('REVOKE ALL ON TABLE public.%I FROM PUBLIC', item.relname);
        FOREACH client_role IN ARRAY ARRAY['anon','authenticated'] LOOP
          IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname=client_role) THEN
            EXECUTE format('REVOKE ALL ON TABLE public.%I FROM %I', item.relname, client_role);
          END IF;
        END LOOP;
        IF item.relname <> 'alembic_version' THEN
          EXECUTE format('GRANT SELECT,INSERT,UPDATE,DELETE ON public.%I TO trifecta_runtime', item.relname);
          EXECUTE format('CREATE POLICY backend_only ON public.%I TO trifecta_runtime USING (true) WITH CHECK (true)', item.relname);
        END IF;
      END LOOP;
      FOREACH client_role IN ARRAY ARRAY['anon','authenticated'] LOOP
        IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname=client_role) THEN
          EXECUTE format('ALTER DEFAULT PRIVILEGES IN SCHEMA public REVOKE ALL ON TABLES FROM %I', client_role);
        END IF;
      END LOOP;
      ALTER DEFAULT PRIVILEGES IN SCHEMA public REVOKE ALL ON TABLES FROM PUBLIC;
      ALTER DEFAULT PRIVILEGES IN SCHEMA public REVOKE EXECUTE ON FUNCTIONS FROM PUBLIC;
      IF to_regprocedure('public.rls_auto_enable()') IS NOT NULL THEN
        REVOKE ALL ON FUNCTION public.rls_auto_enable() FROM PUBLIC;
        FOREACH client_role IN ARRAY ARRAY['anon','authenticated'] LOOP
          IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname=client_role) THEN
            EXECUTE format('REVOKE ALL ON FUNCTION public.rls_auto_enable() FROM %I', client_role);
          END IF;
        END LOOP;
      END IF;
    END $hardening$;
    """)
    op.execute("CREATE SCHEMA IF NOT EXISTS app_private")
    op.execute("REVOKE ALL ON SCHEMA app_private FROM PUBLIC")
    op.execute("GRANT USAGE ON SCHEMA app_private TO trifecta_runtime")
    # Plain PostgreSQL test installations may not include Supabase Auth.
    # Deployed API requests fail closed if this function is absent.
    op.execute("""
    DO $session_setup$ BEGIN
      IF to_regclass('auth.sessions') IS NOT NULL AND to_regclass('auth.users') IS NOT NULL THEN
        EXECUTE $definition$
          CREATE FUNCTION app_private.session_active(session_id uuid, user_id uuid)
          RETURNS boolean LANGUAGE sql STABLE SECURITY DEFINER SET search_path = '' AS $body$
            SELECT EXISTS (
              SELECT 1 FROM auth.sessions s JOIN auth.users u ON u.id=s.user_id
              WHERE s.id=$1 AND s.user_id=$2
                AND (s.not_after IS NULL OR s.not_after > now())
                AND u.deleted_at IS NULL
                AND (u.banned_until IS NULL OR u.banned_until <= now())
                AND u.email_confirmed_at IS NOT NULL AND NOT coalesce(u.is_anonymous,false)
            )
          $body$
        $definition$;
        REVOKE ALL ON FUNCTION app_private.session_active(uuid,uuid) FROM PUBLIC;
        GRANT EXECUTE ON FUNCTION app_private.session_active(uuid,uuid) TO trifecta_runtime;
      END IF;
    END $session_setup$;
    """)


def downgrade() -> None:
    op.execute("DROP FUNCTION IF EXISTS app_private.session_active(uuid,uuid)")
    op.execute("""DO $policies$ DECLARE item record; BEGIN
      FOR item IN SELECT tablename FROM pg_policies WHERE schemaname='public'
                  AND policyname='backend_only' LOOP
        EXECUTE format('DROP POLICY backend_only ON public.%I',item.tablename);
      END LOOP;
    END $policies$""")
    op.drop_index("ix_api_rate_windows_expiry", table_name="api_rate_windows")
    op.drop_table("api_rate_windows")
    # Deliberately do not restore excessive client grants or drop a shared runtime role/schema.
