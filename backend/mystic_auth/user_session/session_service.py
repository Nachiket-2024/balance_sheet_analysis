import traceback
from datetime import UTC, datetime

from fastapi import Request
from sqlalchemy.ext.asyncio import AsyncSession

from ..auth.security.client_ip import get_client_ip
from ..auth.token_logic.jwt_service import jwt_service
from ..auth.token_logic.token_version_store import TokenVersionUnavailableError
from ..logging.logging_config import get_logger
from ..user.user_crud_collector import user_crud
from .session_events import publish_session_created, publish_session_revoked
from .session_geolocation import resolve_city_country
from .session_model import UserSession
from .session_repository import session_repository

logger = get_logger(__name__)


def _to_datetime(exp: int | float | str) -> datetime:
    return datetime.fromtimestamp(float(exp), tz=UTC)


class SessionService:
    """
    Best-effort session-tracking layer sitting alongside the actual
    Postgres-backed version counters (jwt_service.py: account_ver, chain_ver)
    that govern real token validity: every method here catches and logs
    rather than raising, the same reasoning as audit_log_service.
    log_security_event, so a tracking failure (or `db=None`, the same
    test-only convenience that service uses) can never break login/refresh/
    logout.
    """

    @staticmethod
    async def create_session(
        db: AsyncSession | None,
        user_id: int,
        jti: str,
        chain_id: str,
        exp: int | float | str,
        request: Request | None,
        email: str | None = None,
    ) -> None:
        if db is None:
            return
        try:
            user_agent = request.headers.get("user-agent") if request is not None else None
            ip_address = get_client_ip(request) if request is not None else None
            city, country = resolve_city_country(ip_address)
            await session_repository.create(
                db, user_id, jti, chain_id, _to_datetime(exp), user_agent, ip_address, city, country
            )
            # Real-time nudge for any tab already open on this account (see
            # publish_session_created's own docstring). email is optional
            # only because a couple of tests call create_session directly
            # without it; both real login paths (login_service.py,
            # oauth2_service.py) always pass it.
            if email:
                await publish_session_created(email)
        except Exception:
            logger.warning("Failed to record new session:\n%s", traceback.format_exc())

    @staticmethod
    async def rotate_session(
        db: AsyncSession | None,
        old_jti: str,
        new_jti: str,
        chain_id: str,
        new_exp: int | float | str,
        email: str | None = None,
        request: Request | None = None,
    ) -> None:
        if db is None:
            return
        try:
            rotated = await session_repository.rotate(db, old_jti, new_jti, _to_datetime(new_exp))

            # No row matched the old jti: either this session predates the
            # Manage Sessions feature (it logged in before this table
            # existed, so create_session never ran for it) or the original
            # create_session call failed silently. Backfilling here means
            # every still-active session picks up a row within one
            # access-token lifetime (the next time it refreshes) instead of
            # staying invisible forever without a fresh login.
            if rotated is None and email:
                user = await user_crud.get_by_email(email, db)
                if user:
                    user_agent = request.headers.get("user-agent") if request is not None else None
                    ip_address = get_client_ip(request) if request is not None else None
                    city, country = resolve_city_country(ip_address)
                    await session_repository.create(
                        db, user.id, new_jti, chain_id, _to_datetime(new_exp), user_agent, ip_address, city, country
                    )
        except Exception:
            logger.warning("Failed to rotate session jti:\n%s", traceback.format_exc())

    @staticmethod
    async def revoke_session_on_logout(db: AsyncSession | None, jti: str | None, email: str | None) -> bool:
        """Ends exactly the one session this refresh token belongs to:
        bumps its chain's durable Postgres version (so it, and any access token
        sharing it, stop working immediately) and deletes the matching
        Manage Sessions mirror row. This is what a plain, single-device
        Logout actually does. Without the chain bump, a refresh token
        that leaked before logout would remain valid (by version) until it
        naturally expired, since clearing the browser's cookie only stops
        this one client from presenting it again.

        Returns False only when the chain-version bump could not be
        confirmed (Postgres unavailable) - logout_handler.py still clears
        cookies and reports success either way (the caller's own browser
        session is gone regardless), but surfaces this in the response so
        a leaked token surviving the "logout" isn't silently invisible.
        True in every other case, including "nothing to revoke" (already
        logged out, or db/jti unavailable), since none of those represent
        a failed revoke."""
        if db is None or not jti:
            return True
        try:
            session = await session_repository.get_by_jti(db, jti)
            if session is None:
                return True

            if email and session.chain_id:
                if not await jwt_service.bump_chain_version(email, session.chain_id):
                    logger.warning(
                        "Chain version bump could not be confirmed on logout for %s/%s",
                        email, session.chain_id,
                    )
                    return False
                await publish_session_revoked(email)

            await session_repository.revoke_by_jti(db, jti)
            return True
        except Exception:
            logger.warning("Failed to mark session revoked on logout:\n%s", traceback.format_exc())
            return True

    @staticmethod
    async def revoke_all_sessions(
        db: AsyncSession | None, email: str | None, exempt_chain_id: str | None = None
    ) -> None:
        """Mark sessions revoked in Postgres.

        refresh_token_service performs the matching JWT version bump. When
        exempt_chain_id is provided, that chain is kept active so the password
        change flow can replace its tokens without logging out the device.
        """
        if db is None or not email:
            return
        try:
            user = await user_crud.get_by_email(email, db)
            if user:
                if exempt_chain_id:
                    await session_repository.revoke_all_for_user_except_chain(db, user.id, exempt_chain_id)
                else:
                    await session_repository.revoke_all_for_user(db, user.id)
        except Exception:
            logger.warning("Failed to mark all sessions revoked for %s:\n%s", email, traceback.format_exc())

    @staticmethod
    async def rotate_session_by_chain(
        db: AsyncSession | None,
        chain_id: str,
        new_jti: str,
        new_exp: int | float | str,
        email: str | None = None,
        request: Request | None = None,
    ) -> None:
        """Record fresh tokens for a chain exempted from account-wide revoke."""
        if db is None:
            return
        try:
            rotated = await session_repository.rotate_by_chain_id(db, chain_id, new_jti, _to_datetime(new_exp))

            if rotated is None and email:
                user = await user_crud.get_by_email(email, db)
                if user:
                    user_agent = request.headers.get("user-agent") if request is not None else None
                    ip_address = get_client_ip(request) if request is not None else None
                    city, country = resolve_city_country(ip_address)
                    await session_repository.create(
                        db, user.id, new_jti, chain_id, _to_datetime(new_exp), user_agent, ip_address, city, country
                    )
        except Exception:
            logger.warning("Failed to rotate session by chain %s:\n%s", chain_id, traceback.format_exc())

    @staticmethod
    async def revoke_chain(db: AsyncSession | None, chain_id: str) -> None:
        """Mark one chain revoked in Postgres.

        Used by reuse detection when chain_id is the only session identity.
        refresh_token_service.revoke_chain_for_user also bumps the durable Postgres chain
        version.
        """
        if db is None:
            return
        try:
            await session_repository.revoke_by_chain_id(db, chain_id)
        except Exception:
            logger.warning("Failed to mark chain %s revoked:\n%s", chain_id, traceback.format_exc())

    @staticmethod
    async def list_sessions(db: AsyncSession, email: str) -> list[UserSession]:
        user = await user_crud.get_by_email(email, db)
        if not user:
            return []
        return await session_repository.list_active_for_user(db, user.id)

    @staticmethod
    async def count_active_sessions(db: AsyncSession | None, email: str) -> int:
        if db is None:
            return 0
        user = await user_crud.get_by_email(email, db)
        if not user:
            return 0
        return await session_repository.count_active_for_user(db, user.id)

    @staticmethod
    async def revoke_one_session(db: AsyncSession, email: str, session_id: int) -> UserSession | None:
        """Ownership-checked revoke of exactly one session: bumps its
        chain's Postgres version FIRST, then revokes the row, so the two never
        disagree about whether that device is actually still logged in.
        Returns a detached snapshot of the now-deleted row, or None if it
        didn't exist or belonged to a different user - an already-revoked
        session no longer needs its own case, since revoke_by_id deletes the
        row outright, so a second attempt just finds nothing there (the
        handler turns either "didn't exist" case into a 404).

        Raises TokenVersionUnavailableError if the chain-version bump could
        not be confirmed (Postgres unavailable): the Postgres row is
        deliberately left untouched in that case (see session_revoke_handler.py,
        which turns this into a 503 rather than a false "Session revoked").
        Ending a session is this endpoint's entire purpose, so unlike
        logout/password-change it must not report success when that purpose
        wasn't actually achieved."""
        user = await user_crud.get_by_email(email, db)
        if not user:
            return None

        target = await session_repository.get_by_id(db, session_id)
        if target is None or target.user_id != user.id:
            return None

        if target.chain_id and not await jwt_service.bump_chain_version(email, target.chain_id):
            raise TokenVersionUnavailableError(f"Failed to bump chain version for {email}/{target.chain_id}")

        session = await session_repository.revoke_by_id(db, session_id, user.id)
        if session is None:
            return None

        # Real-time nudge: the device that OWNED this session (not the
        # caller doing the revoking) is the one that needs to find out its
        # session just ended. See publish_session_revoked.
        await publish_session_revoked(email)
        return session


session_service = SessionService()
