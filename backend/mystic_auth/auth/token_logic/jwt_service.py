import asyncio
import traceback
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

import jwt
from sqlalchemy import text

from ...core.settings import settings
from ...database.connection import database
from ...logging.logging_config import get_logger
from ...valkey.client import valkey_client
from .token_version_store import TokenVersionUnavailableError, token_version_store

logger = get_logger(__name__)


@dataclass(frozen=True)
class RefreshRotationClaim:
    claimed: bool
    consumed_at: datetime | None
    account_ver: int | None
    chain_ver: int | None
    client_ip: str | None
    legacy_valkey_marker: bool = False


class JWTService:
    """
    Creates, verifies, and revokes access/refresh JWTs.

    Revocation is version-based, not identity-based: a token is valid only
    if its own embedded account_ver and chain_ver still match the durable
    revocation store's current values (Valkey is only a cache; see
    ACCOUNT_VERSION_KEY/CHAIN_VERSION_KEY above).
    Rotation replay protection (a refresh token must only ever be redeemed
    once) is a separate, narrower concern - see claim_jti_for_rotation -
    solved by a short-lived per-jti marker, since versioning alone can't
    tell "already used once" from "still current."
    """

    async def create_access_token(
        self,
        email: str,
        chain_id: str,
        *,
        issued_at: datetime | None = None,
        account_ver: int | None = None,
        chain_ver: int | None = None,
    ) -> str:
        now = issued_at or datetime.now(UTC)
        expire = now + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
        jti = uuid.uuid4().hex

        if account_ver is None or chain_ver is None:
            account_ver, chain_ver = await self.get_token_versions(email, chain_id)

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
            "iss": settings.JWT_ISSUER,
            "aud": settings.JWT_AUDIENCE,
        }

        return await asyncio.to_thread(jwt.encode, payload, settings.SECRET_KEY, settings.JWT_ALGORITHM)

    async def create_refresh_token(
        self,
        email: str,
        chain_id: str,
        *,
        issued_at: datetime | None = None,
        account_ver: int | None = None,
        chain_ver: int | None = None,
    ) -> str:
        """
        chain_id identifies one continuous login, unchanged across every
        rotation of it: a fresh login mints a new random one (see
        login_service.py/oauth2_service.py), while refresh_token_service.
        refresh_tokens() passes the old token's own chain_id back in so its
        successor stays part of the same chain. This is what lets a
        targeted revoke (logout, Manage Sessions, reuse-detection) end
        exactly this one session via bump_chain_version, without touching
        any other session on the account - see
        docs/mystic_auth/authentication/session-management/README.md.
        """
        now = issued_at or datetime.now(UTC)
        expire = now + timedelta(minutes=settings.REFRESH_TOKEN_EXPIRE_MINUTES)
        jti = uuid.uuid4().hex

        if account_ver is None or chain_ver is None:
            account_ver, chain_ver = await self.get_token_versions(email, chain_id)

        payload = {
            "email": email,
            "type": "refresh",
            "jti": jti,
            "chain": chain_id,
            "account_ver": account_ver,
            "chain_ver": chain_ver,
            "iat": now.timestamp(),
            "exp": expire,
            "iss": settings.JWT_ISSUER,
            "aud": settings.JWT_AUDIENCE,
        }

        return await asyncio.to_thread(jwt.encode, payload, settings.SECRET_KEY, settings.JWT_ALGORITHM)

    async def create_verification_token(self, email: str, expires_minutes: int | None = None) -> str:
        """type="verify" (rather than "access") scopes this token to the
        verify-account endpoint only: every protected route requires
        expected_type="access" via verify_token, so a verification token is
        rejected everywhere else in the app even if it leaks (e.g. via an
        email log or forward). Single-use is enforced by its own Valkey key
        (account_verification_service's "verify:{token}"), not by anything
        in this class - it carries no account_ver/chain_ver/jti of its own.

        expires_minutes must match the caller's own single-use Valkey key TTL
        and the expiry stated in the verification email. Previously this
        was hardcoded to ACCESS_TOKEN_EXPIRE_MINUTES (15min default) while
        account_verification_service set the Valkey key TTL and emailed
        wording using RESET_TOKEN_EXPIRE_MINUTES (60min default), so a user
        clicking the link between 15-60 minutes in got a confusing
        invalid/expired error despite the email promising it should still
        work."""
        expire = datetime.now(UTC) + timedelta(
            minutes=expires_minutes if expires_minutes is not None else settings.ACCESS_TOKEN_EXPIRE_MINUTES
        )
        jti = uuid.uuid4().hex

        payload = {
            "email": email,
            "type": "verify",
            "jti": jti,
            "exp": expire,
            "iss": settings.JWT_ISSUER,
            "aud": settings.JWT_AUDIENCE,
        }

        return await asyncio.to_thread(jwt.encode, payload, settings.SECRET_KEY, settings.JWT_ALGORITHM)

    async def verify_token(self, token: str, expected_type: str | None = None) -> dict | None:
        """
        expected_type, if given, must match the token's "type" claim (e.g.
        "access" or "refresh"), otherwise the token is rejected. Pass None to
        skip the check (e.g. for tokens that predate the "type" claim, such as
        password reset tokens).
        """
        try:
            # `algorithms` must be a list, not a bare string: PyJWT treats a
            # string as a Sequence[str] too, turning its membership check
            # into an accidental substring match.
            #
            # verify_aud=False: PyJWT auto-rejects any payload with an "aud"
            # claim present at all, which would break tokens minted before
            # that claim existed. has_valid_issuer_and_audience() below does
            # the real iss/aud check instead, with "absent is fine,
            # present-and-wrong is not" semantics.
            payload = await asyncio.to_thread(
                jwt.decode,
                token,
                settings.SECRET_KEY,
                algorithms=[settings.JWT_ALGORITHM],
                options={"verify_aud": False},
            )

            if not self.has_valid_issuer_and_audience(payload):
                return None

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
        Valkey already shows as revoked, we still need to know which user it
        belonged to so we can revoke their other active sessions. verify_token
        can't be used for that because it would correctly refuse to return a
        payload for a revoked token.
        """
        try:
            # verify_aud disabled here too: this method's contract is
            # "signature and expiry only" (see docstring above), and an
            # unconditioned jwt.decode auto-rejects on the mere presence of
            # an "aud" claim - see verify_token's own comment on the same
            # options= kwarg for why.
            return await asyncio.to_thread(
                jwt.decode,
                token,
                settings.SECRET_KEY,
                algorithms=[settings.JWT_ALGORITHM],
                options={"verify_aud": False},
            )

        except jwt.PyJWTError:
            return None

    async def is_benign_duplicate_rotation(self, jti: str, client_ip: str | None) -> bool:
        """Recognize a same-IP retry during the short rotation grace window.

        The retry is rejected without minting another token pair or revoking
        the chain created by the successful first request.
        """
        grace = settings.REFRESH_TOKEN_REUSE_GRACE_SECONDS
        if grace <= 0:
            return False
        try:
            async with database.async_session() as session:
                result = await session.execute(
                    text(
                        "SELECT consumed_at, client_ip FROM consumed_refresh_tokens "
                        "WHERE jti = :jti"
                    ),
                    {"jti": jti},
                )
                row = result.first()
            if row is None:
                # A short compatibility window for claim markers created by
                # the previous release during a rolling deployment. Those
                # legacy markers cannot reproduce their random child pair.
                marker = await valkey_client.get(f"revoked:{jti}")
                if isinstance(marker, bytes):
                    marker = marker.decode()
                if not isinstance(marker, str) or "|" not in marker:
                    return False
                claimed_at, claimed_ip = marker.split("|", 1)
                age = datetime.now(UTC).timestamp() - float(claimed_at)
                return 0 <= age <= grace and claimed_ip == (client_ip or "")
            consumed_at, claimed_ip = row
            age = (datetime.now(UTC) - consumed_at).total_seconds()
            return 0 <= age <= grace and claimed_ip == client_ip
        except Exception as error:
            logger.error("Failed to read durable refresh rotation for jti %s:\n%s", jti, traceback.format_exc())
            raise TokenVersionUnavailableError("durable refresh rotation store unavailable") from error

    async def claim_jti_for_rotation(
        self,
        jti: str,
        exp: int | float | None,
        email: str | None = None,
        client_ip: str | None = None,
        account_ver: int = 0,
        chain_ver: int = 0,
    ) -> RefreshRotationClaim:
        """
        Atomically marks jti as redeemed, only if it wasn't already -
        refresh tokens are single-use, so this is what actually stops the
        exact same token being redeemed twice (a genuine replay, or two
        concurrent requests racing on it), a narrower problem than "is this
        session still authorized" (account_ver/chain_ver) and not solved by
        it: a stolen-but-still-current-version token could otherwise be
        used to mint an unbounded number of new token pairs. Returns True
        only for the call that actually claimed it (safe to proceed with
        rotation). A retry receives the existing claim and is rejected by
        the refresh service; it cannot mint a second child pair.

        A Postgres unique key makes the check-and-claim atomic and survives
        Valkey flushes/restarts. Rows are retained only until the token's
        expiry and removed by the scheduled session cleanup task. `email` is
        retained for interface compatibility; it is not persisted here.
        """
        try:
            if exp is None:
                raise ValueError("refresh token is missing expiry")
            # Honor markers written by the previous Valkey-only implementation
            # during rolling upgrades. New claims are written to Postgres.
            try:
                if await valkey_client.exists(f"revoked:{jti}") == 1:
                    return RefreshRotationClaim(False, None, None, None, client_ip, True)
            except Exception:
                # The durable PostgreSQL claim below is authoritative. A
                # missing cache during a deployment must not block refresh.
                logger.warning("Could not read legacy Valkey refresh marker for jti %s", jti)
            expiry = datetime.fromtimestamp(float(exp), tz=UTC)
            async with database.async_session() as session:
                result = await session.execute(
                    text(
                        "INSERT INTO consumed_refresh_tokens "
                        "(jti, consumed_at, expires_at, client_ip, account_ver, chain_ver) "
                        "VALUES (:jti, now(), :expires_at, :client_ip, :account_ver, :chain_ver) "
                        "ON CONFLICT (jti) DO NOTHING "
                        "RETURNING consumed_at, client_ip, account_ver, chain_ver"
                    ),
                    {
                        "jti": jti,
                        "expires_at": expiry,
                        "client_ip": client_ip,
                        "account_ver": account_ver,
                        "chain_ver": chain_ver,
                    },
                )
                row = result.first()
                claimed = row is not None
                if row is None:
                    result = await session.execute(
                        text(
                            "SELECT consumed_at, client_ip, account_ver, chain_ver "
                            "FROM consumed_refresh_tokens WHERE jti = :jti"
                        ),
                        {"jti": jti},
                    )
                    row = result.first()
                if row is None:
                    raise RuntimeError("refresh token claim disappeared during transaction")
                await session.commit()
                consumed_at, stored_ip, stored_account_ver, stored_chain_ver = row
                return RefreshRotationClaim(
                    claimed=claimed,
                    consumed_at=consumed_at,
                    account_ver=int(stored_account_ver),
                    chain_ver=int(stored_chain_ver),
                    client_ip=stored_ip,
                )

        except Exception as error:
            logger.error("Failed to claim durable refresh jti %s:\n%s", jti, traceback.format_exc())
            raise TokenVersionUnavailableError("durable refresh rotation store unavailable") from error

    async def is_token_revoked_by_jti(self, jti: str | None) -> bool:
        """Returns False (not just when unrevoked) when no jti was given:
        tokens minted outside jwt_service, such as password reset tokens,
        carry no jti and were never eligible for this check."""
        if not jti:
            return False

        return await valkey_client.exists(f"revoked:{jti}") == 1

    def has_valid_issuer_and_audience(self, payload: dict) -> bool:
        """False (reject) only when "iss"/"aud" is present and wrong; True
        (including for a token minted before this feature shipped, carrying
        neither claim) whenever there's nothing to compare against - same
        "nothing to check against, so don't reject" reasoning as
        is_current_version's account_ver/chain_ver checks and
        is_token_revoked_by_jti's jti-less early return.

        Checked outside jwt.decode's own audience=/issuer= kwargs
        (rather than passed to it) deliberately: those raise/reject the
        instant the claim is *missing*, which would be a hard break for
        any token minted before JWT_ISSUER/JWT_AUDIENCE existed, instead of
        the graceful, additive rollout every other claim in this class gets.
        """
        iss = payload.get("iss")
        if iss is not None and iss != settings.JWT_ISSUER:
            return False

        aud = payload.get("aud")
        return aud is None or aud == settings.JWT_AUDIENCE

    # Account/chain version reads and bumps live in token_version_store.py
    # (Postgres-backed revocation bookkeeping), re-exported here as bound
    # methods so every existing `jwt_service.get_account_version(...)`-style
    # call site keeps working unchanged.
    get_account_version = token_version_store.get_account_version
    get_chain_version = token_version_store.get_chain_version
    get_token_versions = token_version_store.get_versions
    bump_account_version = token_version_store.bump_account_version
    bump_chain_version = token_version_store.bump_chain_version

    async def is_current_version(self, payload: dict) -> bool:
        """False (revoked) if either the token's embedded account_ver or
        chain_ver has fallen behind the durable store's current value. True (including
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
