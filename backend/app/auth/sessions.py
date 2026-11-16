"""Use Supabase's authoritative session state for authenticated API requests."""

import uuid

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.verifier import AuthenticationError, VerifiedIdentity


async def require_active_session(session: AsyncSession, identity: VerifiedIdentity) -> None:
    try:
        session_id = uuid.UUID(str(identity.claims.get("session_id", "")))
    except (ValueError, TypeError) as exc:
        raise AuthenticationError("Invalid session.") from exc
    active = await session.scalar(
        text("SELECT app_private.session_active(:session_id, :user_id)"),
        {"session_id": session_id, "user_id": identity.user_id},
    )
    if not active:
        raise AuthenticationError("Invalid session.")
