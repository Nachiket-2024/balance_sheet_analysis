import asyncio
import traceback
import uuid
from datetime import UTC, datetime, timedelta

import jwt

from ...core.settings import settings
from ...logging.logging_config import get_logger
from ...redis.client import redis_client

logger = get_logger(__name__)

# Redis key for a user's account-wide token version: every access/refresh
# token embeds the version that was current when it was minted (see
# create_access_token/create_refresh_token), and is rejected the moment
# that number no longer matches. Bumping this one integer (bump_account_version)
# is what "logout everywhere" actually is - no per-token bookkeeping, no
# iterating anything: every token on the account, minted before the bump,
# stops matching in one atomic INCR. Never expires: it has to keep meaning
# the same thing for as long as the account exists, since a token minted
# long after the last bump must still match it correctly.
ACCOUNT_VERSION_KEY = "account_ver:{email}"

# Redis key for one login's version, scoped to its chain_id (see
# create_refresh_token's own docstring for what a chain is). Bumping this
# (bump_chain_version) ends exactly that one session - logout, a targeted
# Manage Sessions revoke, or reuse-detection containing a compromised
# chain - without touching any other session on the account. TTL'd to the
# refresh-token lifetime on bump: once that elapses, nothing could still be
# validly using this chain_id anyway (a fresh login never reuses an old
# chain_id), so the key can safely disappear instead of accumulating one
# per revoked session forever.
CHAIN_VERSION_KEY = "chain_ver:{email}:{chain_id}"


class JWTService:
    """
    Creates, verifies, and revokes access/refresh JWTs.

    Revocation is version-based, not identity-based: a token is valid only
    if its own embedded account_ver and chain_ver still match Redis's
    current values (see ACCOUNT_VERSION_KEY/CHAIN_VERSION_KEY above).
    Rotation replay protection (a refresh token must only ever be redeemed
    once) is a separate, narrower concern - see claim_jti_for_rotation -
    solved by a short-lived per-jti marker, since versioning alone can't
    tell "already used once" from "still current."
    """

    async def create_access_token(self, email: str, chain_id: str) -> str:
        now = datetime.now(UTC)
        expire = now + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
        jti = uuid.uuid4().hex

        account_ver, chain_ver = await asyncio.gather(
            self.get_account_version(email), self.get_chain_version(email, chain_id)
        )

        # "iat" is a float (now.timestamp()), not the datetime object
        # itself: PyJWT truncates a datetime-valued exp/iat/nbf claim to
        # whole seconds while encoding (calendar.timegm() drops the
        # microseconds). Nothing here actually compares "iat" anymore
        # (revocation is purely version-based), but callers/tests still
        # read it as "when was this minted", so it keeps real precision
        # rather than silently losing it for no reason.
        payload = {
            "email": email,
            "type": "access",
            "jti": jti,
            "chain": chain_id,
            "account_ver": account_ver,
            "chain_ver": chain_ver,
            "iat": now.timestamp(),
            "exp": expire,
        }

        return await asyncio.to_thread(jwt.encode, payload, settings.SECRET_KEY, settings.JWT_ALGORITHM)

    async def create_refresh_token(self, email: str, chain_id: str) -> str:
        """
        chain_id identifies one continuous login, unchanged across every
        rotation of it: a fresh login mints a new random one (see
        login_service.py/oauth2_service.py), while refresh_token_service.
        refresh_tokens() passes the old token's own chain_id back in so its
        successor stays part of the same chain. This is what lets a
        targeted revoke (logout, Manage Sessions, reuse-detection) end
        exactly this one session via bump_chain_version, without touching
        any other session on the account - see
        docs/mystic_auth/authentication/session-management.md.
        """
        now = datetime.now(UTC)
        expire = now + timedelta(minutes=settings.REFRESH_TOKEN_EXPIRE_MINUTES)
        jti = uuid.uuid4().hex

        account_ver, chain_ver = await asyncio.gather(
            self.get_account_version(email), self.get_chain_version(email, chain_id)
        )

        payload = {
            "email": email,
            "type": "refresh",
            "jti": jti,
            "chain": chain_id,
            "account_ver": account_ver,
            "chain_ver": chain_ver,
            "iat": now.timestamp(),
            "exp": expire,
        }

        return await asyncio.to_thread(jwt.encode, payload, settings.SECRET_KEY, settings.JWT_ALGORITHM)

    async def create_verification_token(self, email: str, expires_minutes: int | None = None) -> str:
        """type="verify" (rather than "access") scopes this token to the
        verify-account endpoint only: every protected route requires
        expected_type="access" via verify_token, so a verification token is
        rejected everywhere else in the app even if it leaks (e.g. via an
        email log or forward). Single-use is enforced by its own Redis key
        (account_verification_service's "verify:{token}"), not by anything
        in this class - it carries no account_ver/chain_ver/jti of its own.

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

            if not await self.is_current_version(payload):
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

    async def claim_jti_for_rotation(self, jti: str, exp: int | float | None, email: str | None = None) -> bool:
        """
        Atomically marks jti as redeemed, only if it wasn't already -
        refresh tokens are single-use, so this is what actually stops the
        exact same token being redeemed twice (a genuine replay, or two
        concurrent requests racing on it), a narrower problem than "is this
        session still authorized" (account_ver/chain_ver) and not solved by
        it: a stolen-but-still-current-version token could otherwise be
        used to mint an unbounded number of new token pairs. Returns True
        only for the call that actually claimed it (safe to proceed with
        rotation), False if it was already claimed.

        SET...NX makes the check-and-claim one atomic Redis operation:
        a separate is_token_revoked_by_jti-then-mark pair would leave a
        real gap where two concurrent requests presenting the identical
        refresh token could both observe "not yet claimed" and both
        proceed to mint a fresh token pair from one token. `email` is
        currently unused here (retained for interface symmetry with
        callers that pass it) - the jti-registry cleanup this used to
        also perform no longer exists now that revocation is version-based.
        """
        try:
            ttl = 1
            if exp is not None:
                ttl = max(1, int(exp - datetime.now(UTC).timestamp()))

            claimed = await redis_client.set(f"revoked:{jti}", "true", nx=True, ex=ttl)

            return bool(claimed)

        except Exception:
            logger.warning("Failed to claim jti %s for rotation:\n%s", jti, traceback.format_exc())
            return False

    async def is_token_revoked_by_jti(self, jti: str | None) -> bool:
        """Returns False (not just when unrevoked) when no jti was given:
        tokens minted outside jwt_service, such as password reset tokens,
        carry no jti and were never eligible for this check."""
        if not jti:
            return False

        return await redis_client.exists(f"revoked:{jti}") == 1

    async def get_account_version(self, email: str) -> int:
        """Current account-wide version, 0 if it has never been bumped
        (i.e. this account has never had a whole-account revoke)."""
        try:
            raw = await redis_client.get(ACCOUNT_VERSION_KEY.format(email=email))
            return int(raw) if raw is not None else 0
        except Exception:
            logger.warning("Failed to read account version for %s:\n%s", email, traceback.format_exc())
            return 0

    async def get_chain_version(self, email: str, chain_id: str) -> int:
        """Current version for one chain, 0 if it has never been bumped
        (i.e. this specific session has never been individually revoked)."""
        try:
            raw = await redis_client.get(CHAIN_VERSION_KEY.format(email=email, chain_id=chain_id))
            return int(raw) if raw is not None else 0
        except Exception:
            logger.warning(
                "Failed to read chain version for %s/%s:\n%s", email, chain_id, traceback.format_exc()
            )
            return 0

    async def bump_account_version(self, email: str) -> None:
        """The whole-account revoke: logout-all, password change, account
        deactivation/purge, and reuse-detection on a token with no chain
        claim of its own (unknown lineage, so the maximally-safe response).
        Every token on the account, minted before this call, stops
        matching on its very next use."""
        try:
            await redis_client.incr(ACCOUNT_VERSION_KEY.format(email=email))
        except Exception:
            logger.warning("Failed to bump account version for %s:\n%s", email, traceback.format_exc())

    async def bump_chain_version(self, email: str, chain_id: str) -> None:
        """The single-session revoke: logout (this device only), a
        targeted Manage Sessions "End session", and reuse-detection scoped
        to the compromised chain specifically. Every token sharing this
        chain_id, minted before this call, stops matching on its next use;
        every other chain on the account is completely unaffected."""
        try:
            key = CHAIN_VERSION_KEY.format(email=email, chain_id=chain_id)
            await redis_client.incr(key)
            await redis_client.expire(key, settings.REFRESH_TOKEN_EXPIRE_MINUTES * 60)
        except Exception:
            logger.warning(
                "Failed to bump chain version for %s/%s:\n%s", email, chain_id, traceback.format_exc()
            )

    async def is_current_version(self, payload: dict) -> bool:
        """False (revoked) if either the token's embedded account_ver or
        chain_ver has fallen behind Redis's current value. True (including
        for a token minted before this feature shipped, carrying neither
        claim) whenever there's nothing to compare - same "nothing to check
        against, so don't reject" reasoning as the jti-less early return in
        is_token_revoked_by_jti.

        Public (not just used internally by verify_token): refresh_token_
        service.refresh_tokens() also calls this directly, since rotation
        deliberately bypasses verify_token itself (see that method's own
        comment on why) but must still reject a refresh token that a
        whole-account or single-chain revoke already invalidated - without
        this, a stale-but-still-unused refresh token could keep minting
        fresh sessions indefinitely after logout-all/a password change/a
        targeted Manage Sessions revoke, since claim_jti_for_rotation alone
        only catches a token being reused, not one that's simply stale."""
        email = payload.get("email")
        if not email:
            return True

        account_ver = payload.get("account_ver")
        if account_ver is not None and int(account_ver) != await self.get_account_version(email):
            return False

        chain_id = payload.get("chain")
        chain_ver = payload.get("chain_ver")
        return not (
            chain_id and chain_ver is not None and int(chain_ver) != await self.get_chain_version(email, chain_id)
        )


jwt_service = JWTService()
