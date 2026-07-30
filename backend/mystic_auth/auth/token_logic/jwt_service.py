import asyncio
import traceback
import uuid
from datetime import UTC, datetime, timedelta
from typing import cast

import jwt

from ...core.settings import settings
from ...logging.logging_config import get_logger
from ...redis.client import redis_client

logger = get_logger(__name__)

# Redis key template for a user's refresh-token registry (a jti -> expiry Hash).
# Deliberately NOT named "user:{email}:refresh_tokens": that name was used
# pre-jti-migration for a Redis SET of raw tokens. Reusing the same key name
# for an incompatible type (Set -> Hash) would make HSET/HGETALL/HDEL raise
# WRONGTYPE against any Redis instance that still holds the old Set from
# before this change, breaking login/refresh/logout-all for every
# already-authenticated user until an operator manually deletes the key. A
# fresh key name sidesteps the collision entirely; old Set-typed keys are
# simply never touched again (they were never given a TTL either, so a
# deployment migrating this template into a live app with existing session
# data should still plan an explicit cleanup of the old key pattern).
REFRESH_TOKEN_REGISTRY_KEY = "refresh_token_registry:{email}"


class JWTService:
    """
    Creates, verifies, and revokes access/refresh JWTs.

    Revocation and session tracking are keyed by the token's "jti" claim rather
    than the raw JWT string. Keying off the raw token would mean every valid,
    unexpired refresh token sits in Redis in cleartext (in the per-user session
    set), so anyone with read access to Redis (a backup, a misconfigured replica,
    a compromised monitoring tool) could lift a token straight out and use it
    without ever touching the database or the JWT secret. A jti is a random,
    otherwise-meaningless identifier: it lets us blacklist/track a specific
    token without Redis ever holding a credential that's usable on its own.
    """

    async def create_access_token(self, email: str) -> str:
        expire = datetime.now(UTC) + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
        jti = uuid.uuid4().hex

        # The "type" claim lets verify_token tell access and refresh tokens
        # apart; the "jti" claim gives revocation/session tracking something to
        # key off of other than the raw token string.
        payload = {"email": email, "type": "access", "jti": jti, "exp": expire}

        return await asyncio.to_thread(jwt.encode, payload, settings.SECRET_KEY, settings.JWT_ALGORITHM)

    async def create_refresh_token(self, email: str) -> str:
        expire = datetime.now(UTC) + timedelta(minutes=settings.REFRESH_TOKEN_EXPIRE_MINUTES)
        jti = uuid.uuid4().hex

        payload = {"email": email, "type": "refresh", "jti": jti, "exp": expire}

        token = await asyncio.to_thread(jwt.encode, payload, settings.SECRET_KEY, settings.JWT_ALGORITHM)

        # Record jti -> expiry (epoch seconds) in the user's refresh-token
        # registry, never the raw token itself.
        registry_key = REFRESH_TOKEN_REGISTRY_KEY.format(email=email)
        await redis_client.hset(registry_key, jti, int(expire.timestamp()))

        # A jti is only ever removed from this hash by an explicit
        # revoke/rotation/logout-all: a refresh token that's simply never
        # used again (the common case: a session that quietly goes stale)
        # left its entry here forever, growing this hash without bound over
        # a deployment's lifetime. Piggybacking a sweep on every new token
        # mint (login/refresh, the exact moments that grow the hash) keeps
        # it bounded to roughly the user's active session count instead of
        # every refresh token ever issued to them.
        await self._prune_expired_registry_entries(registry_key)

        return token

    async def _prune_expired_registry_entries(self, registry_key: str) -> None:
        try:
            registry = await redis_client.hgetall(registry_key)
            if not registry:
                return

            now = datetime.now(UTC).timestamp()
            expired_jtis = [jti for jti, exp in registry.items() if float(exp) <= now]

            if expired_jtis:
                await redis_client.hdel(registry_key, *expired_jtis)

        except Exception:
            # Best-effort hygiene: must never block minting a new token.
            logger.warning("Failed to prune expired refresh-token registry entries:\n%s", traceback.format_exc())

    async def create_verification_token(self, email: str, expires_minutes: int | None = None) -> str:
        """type="verify" (rather than "access") scopes this token to the
        verify-account endpoint only: every protected route requires
        expected_type="access" via verify_token, so a verification token is
        rejected everywhere else in the app even if it leaks (e.g. via an
        email log or forward).

        expires_minutes must match the caller's own single-use Redis key TTL
        and the expiry stated in the verification email. Previously this
        was hardcoded to ACCESS_TOKEN_EXPIRE_MINUTES (15min default) while
        account_verification_service set the Redis key TTL and emailed
        wording using RESET_TOKEN_EXPIRE_MINUTES (60min default), so a user
        clicking the link between 15-60 minutes in got a confusing
        invalid/expired error despite the email promising it should still
        work."""
        expire = datetime.now(UTC) + timedelta(
            minutes=expires_minutes if expires_minutes is not None else settings.ACCESS_TOKEN_EXPIRE_MINUTES
        )
        jti = uuid.uuid4().hex

        payload = {"email": email, "type": "verify", "jti": jti, "exp": expire}

        return await asyncio.to_thread(jwt.encode, payload, settings.SECRET_KEY, settings.JWT_ALGORITHM)

    async def verify_token(self, token: str, expected_type: str | None = None) -> dict | None:
        """
        expected_type, if given, must match the token's "type" claim (e.g.
        "access" or "refresh"), otherwise the token is rejected. Pass None to
        skip the check (e.g. for tokens that predate the "type" claim, such as
        password reset tokens).
        """
        try:
            # The algorithm allowlist is passed as a single-element list, not a
            # bare string: PyJWT's `algorithms` parameter accepts a bare string
            # as a technically-valid Sequence[str] (Python strings are
            # sequences of characters), which would make its internal
            # membership check an accidental substring match instead of an
            # exact one. A list is the only form PyJWT's own docs endorse for
            # this parameter.
            payload = await asyncio.to_thread(
                jwt.decode, token, settings.SECRET_KEY, algorithms=[settings.JWT_ALGORITHM]
            )

            if await self.is_token_revoked_by_jti(payload.get("jti")):
                return None

            if expected_type is not None and payload.get("type") != expected_type:
                logger.warning(
                    "Token type mismatch: expected '%s', got '%s'",
                    expected_type, payload.get("type"),
                )
                return None

            return payload

        except jwt.ExpiredSignatureError:
            return None

        except jwt.InvalidTokenError:
            return None

        except Exception:
            logger.error("JWT verification error:\n%s", traceback.format_exc())
            return None

    async def decode_payload(self, token: str) -> dict | None:
        """
        Decodes a token's claims checking only signature and expiry, deliberately
        skipping the revocation check performed by verify_token.

        Exists for reuse-detection: when a refresh token is presented that
        Redis already shows as revoked, we still need to know which user it
        belonged to in order to revoke their other active sessions. verify_token
        can't be used for that because it would correctly refuse to return a
        payload for a revoked token.
        """
        try:
            return await asyncio.to_thread(
                jwt.decode, token, settings.SECRET_KEY, algorithms=[settings.JWT_ALGORITHM]
            )

        except jwt.PyJWTError:
            return None

    async def revoke_token(self, token: str, email: str | None = None) -> bool:
        try:
            # Reuses the same canonical decode path as is_token_revoked, rather
            # than re-decoding with a second, separately-maintained jwt.decode call.
            payload = await self.decode_payload(token)

            if not payload:
                logger.warning("Cannot revoke token: decode failed")
                return False

            jti = payload.get("jti")
            exp = payload.get("exp")

            if not jti:
                logger.warning("Cannot revoke token without a jti claim")
                return False

            return await self.revoke_token_by_jti(jti, exp, email)

        except Exception:
            logger.warning("Failed to revoke token:\n%s", traceback.format_exc())
            return False

    async def revoke_token_by_jti(self, jti: str, exp: int | float | None, email: str | None = None) -> bool:
        try:
            # Minimum of 1 second, since Redis requires a positive expiry and an
            # already-expired token still needs its blacklist entry to exist at
            # least momentarily.
            ttl = 1
            if exp is not None:
                ttl = max(1, int(exp - datetime.now(UTC).timestamp()))

            await redis_client.set(f"revoked:{jti}", "true", ex=ttl)

            if email:
                await redis_client.hdel(REFRESH_TOKEN_REGISTRY_KEY.format(email=email), jti)

            return True

        except Exception:
            logger.warning("Failed to revoke jti %s:\n%s", jti, traceback.format_exc())
            return False

    async def claim_jti_for_rotation(self, jti: str, exp: int | float | None, email: str | None = None) -> bool:
        """
        Atomically revokes jti only if it wasn't already revoked. Returns
        True only for the call that actually revoked it (safe to proceed
        with rotation), False if it was already revoked (either a genuine
        replayed refresh token, or a concurrent request that won the race
        first).

        Unlike revoke_token_by_jti (an unconditional overwrite, correct for
        logout/logout-all/account-deletion, where "already revoked" is a
        harmless no-op), this uses SET...NX so the check-and-revoke happen as
        one atomic Redis operation. A separate is_token_revoked_by_jti-then-
        revoke_token_by_jti pair left a real gap: two concurrent requests
        presenting the identical refresh token could both observe "not yet
        revoked" and both proceed to mint a fresh token pair from one token.
        """
        try:
            ttl = 1
            if exp is not None:
                ttl = max(1, int(exp - datetime.now(UTC).timestamp()))

            claimed = await redis_client.set(f"revoked:{jti}", "true", nx=True, ex=ttl)

            if claimed and email:
                await redis_client.hdel(REFRESH_TOKEN_REGISTRY_KEY.format(email=email), jti)

            return bool(claimed)

        except Exception:
            logger.warning("Failed to claim jti %s for rotation:\n%s", jti, traceback.format_exc())
            return False

    async def is_token_revoked_by_jti(self, jti: str | None) -> bool:
        """Returns False (not just when unrevoked) when no jti was given:
        tokens minted outside jwt_service, such as password reset tokens,
        carry no jti and were never eligible for this revocation mechanism."""
        if not jti:
            return False

        return await redis_client.exists(f"revoked:{jti}") == 1

    async def is_token_revoked(self, token: str) -> bool:
        """Convenience wrapper for callers (e.g. reuse detection in
        refresh_token_service) that only have the raw token in hand."""
        payload = await self.decode_payload(token)
        jti = payload.get("jti") if payload else None

        if not jti:
            return False

        return await self.is_token_revoked_by_jti(jti)

    async def get_all_refresh_tokens_for_user(self, email: str) -> dict[str, str]:
        """Returns the user's jti -> expiry (Unix timestamp, as a string)
        registry, or an empty dict if they have no active refresh tokens."""
        # redis-py's hgetall() is typed for both raw-bytes and decoded-str
        # responses; this client is constructed with decode_responses=True
        # (see redis/client.py), so the result is always dict[str, str] here.
        registry = cast(
            "dict[str, str]", await redis_client.hgetall(REFRESH_TOKEN_REGISTRY_KEY.format(email=email))
        )

        return registry or {}


jwt_service = JWTService()
