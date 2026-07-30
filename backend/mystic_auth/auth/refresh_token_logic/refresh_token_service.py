import traceback

from fastapi import Request
from sqlalchemy.ext.asyncio import AsyncSession

# Refresh token reuse is likely theft, not a routine expired/invalid refresh:
# see _handle_reuse_detected.
from ...audit_log.audit_log_service import REFRESH_TOKEN_REUSE_DETECTED, log_security_event
from ...logging.logging_config import get_logger
from ..token_logic.jwt_service import jwt_service

logger = get_logger(__name__)


class RefreshTokenService:
    """Rotates, revokes, and detects reuse of refresh tokens, backed entirely by Redis."""

    @staticmethod
    async def refresh_tokens(
        refresh_token: str, db: AsyncSession | None = None, request: Request | None = None
    ) -> dict[str, str] | None:
        try:
            # Decoded once and threaded through the rest of this method, since a
            # previous version decoded the same token up to three separate times
            # (once each in is_token_revoked, verify_token, and revoke_token) and
            # checked its revocation status against Redis twice. This is the
            # busiest endpoint in the auth system (every refresh happens on every
            # access-token expiry, for every session), so that redundant work mattered.
            payload = await jwt_service.decode_payload(refresh_token)

            if not payload:
                return None

            jti = payload.get("jti")
            if not jti:
                logger.warning("Refresh token payload missing 'jti' claim")
                return None

            # Type is checked before the token is ever claimed/revoked below:
            # a wrong-type token (e.g. an access token mistakenly presented
            # here) must be rejected without side effects, never burned as if
            # it were a real refresh token.
            if payload.get("type") != "refresh":
                logger.warning(
                    "Token type mismatch during refresh: expected 'refresh', got '%s'",
                    payload.get("type"),
                )
                return None

            # Refresh tokens are single-use: claim_jti_for_rotation atomically
            # revokes this jti only if it wasn't already revoked. A revoked jti
            # being presented again means it was replayed: either the
            # legitimate user retried a stale token, two concurrent requests
            # raced on the same token, or the token was stolen and is being
            # used by an attacker in parallel with its rightful owner. Either
            # way, the whole session is now treated as compromised: every
            # refresh token for that user is revoked, forcing re-authentication
            # on all devices. Using one atomic claim (rather than a separate
            # "is it revoked" check followed later by a revoke call) closes a
            # real race: two concurrent requests with the same token could
            # otherwise both pass a read-only check before either revoked it,
            # and both mint a valid new token pair from a single presented token.
            # Checked before requiring email so a reused token missing that
            # claim still gets caught here (_handle_reuse_detected copes with
            # a missing email on its own).
            claimed = await jwt_service.claim_jti_for_rotation(jti, payload.get("exp"), payload.get("email"))
            if not claimed:
                await RefreshTokenService._handle_reuse_detected(payload, db, request)
                return None

            email = payload.get("email")

            if not email:
                return None

            new_access_token = await jwt_service.create_access_token(email)
            new_refresh_token = await jwt_service.create_refresh_token(email)

            return {"access_token": new_access_token, "refresh_token": new_refresh_token}

        except Exception:
            logger.error("Error refreshing token:\n%s", traceback.format_exc())
            return None

    @staticmethod
    async def revoke_refresh_token(refresh_token: str) -> bool:
        try:
            payload = await jwt_service.verify_token(refresh_token, expected_type="refresh")

            if not payload:
                return False

            email = payload.get("email")

            if not email:
                return False

            await jwt_service.revoke_token(refresh_token, email)

            return True

        except Exception:
            logger.error("Error revoking refresh token:\n%s", traceback.format_exc())
            return False

    @staticmethod
    async def revoke_all_tokens_for_user(email: str) -> int:
        try:
            # The registry never holds raw tokens, only jti -> expiry pairs.
            jti_registry = await jwt_service.get_all_refresh_tokens_for_user(email)

            if not jti_registry:
                return 0

            revoked_count = 0

            for jti, exp in jti_registry.items():
                if await jwt_service.revoke_token_by_jti(jti, float(exp), email):
                    revoked_count += 1

            return revoked_count

        except Exception:
            logger.error("Error revoking all tokens for user %s:\n%s", email, traceback.format_exc())
            return 0

    @staticmethod
    async def _handle_reuse_detected(
        payload: dict, db: AsyncSession | None = None, request: Request | None = None
    ) -> None:
        """
        payload is the already-decoded claims of a refresh token whose jti Redis
        shows as already revoked. Accepting it directly avoids decoding the
        token a second time, since the caller already did that once to reach
        this point.
        """
        email = payload.get("email")

        if not email:
            logger.warning("Refresh token reuse detected, but no email claim was present")
            return

        revoked_count = await RefreshTokenService.revoke_all_tokens_for_user(email)

        # Logged at a severity that stands out from routine single-token
        # revocations, since this indicates likely token theft rather than an
        # expected rotation.
        logger.critical(
            "Refresh token reuse detected for %s, revoked %d active session(s)",
            email, revoked_count,
        )

        await log_security_event(
            REFRESH_TOKEN_REUSE_DETECTED,
            db,
            user_email=email,
            success=False,
            request=request,
            metadata={"sessions_revoked": revoked_count},
        )


refresh_token_service = RefreshTokenService()
