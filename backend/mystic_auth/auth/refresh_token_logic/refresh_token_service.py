import traceback

from fastapi import Request
from sqlalchemy.ext.asyncio import AsyncSession

# Refresh token reuse is likely theft, not a routine expired/invalid refresh:
# see _handle_reuse_detected.
from ...audit_log.audit_log_service import REFRESH_TOKEN_REUSE_DETECTED, log_security_event
from ...error_monitoring.sentry_service import capture_security_alert
from ...logging.logging_config import get_logger
from ...user_session.session_events import publish_session_revoked
from ...user_session.session_service import session_service
from ..security.client_ip import get_client_ip
from ..token_logic.jwt_service import jwt_service
from ..token_logic.token_version_store import TokenVersionUnavailableError

logger = get_logger(__name__)


class RefreshTokenService:
    """Rotates and revokes refresh tokens. Revocation is version-based
    (jwt_service.bump_account_version / bump_chain_version), not identity
    based. See jwt_service.py for the version checks."""

    @staticmethod
    async def refresh_tokens(
        refresh_token: str, db: AsyncSession | None = None, request: Request | None = None
    ) -> dict[str, str] | None:
        try:
            # Decoded once and threaded through the rest of this method, since a
            # previous version decoded the same token up to three separate times.
            # This is the busiest endpoint in the auth system (every refresh happens on every
            # access-token expiry, for every session), so that redundant work mattered.
            payload = await jwt_service.decode_payload(refresh_token)

            if not payload:
                return None

            if not jwt_service.has_valid_issuer_and_audience(payload):
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

            # Checked before claiming: a token with a stale account_ver/chain_ver
            # was invalidated by an explicit revoke, not stolen, so this is a
            # quiet rejection, not reuse-detection. Without it, claim_jti_for_rotation
            # alone (which only catches a jti redeemed *twice*) would happily
            # rotate a stale-but-never-used token into a fresh valid session,
            # defeating the revoke that just happened.
            if not await jwt_service.is_current_version(payload):
                return None

            email = payload.get("email")
            chain_id = payload.get("chain")
            if not email or not chain_id:
                return None

            # New tokens carry both snapshots. For a still-valid legacy token
            # that predates version claims, capture current values once so
            # the token's first successful rotation retains a version snapshot.
            account_ver = payload.get("account_ver")
            chain_ver = payload.get("chain_ver")
            if account_ver is None or chain_ver is None:
                current_account_ver, current_chain_ver = await jwt_service.get_token_versions(email, chain_id)
                account_ver = current_account_ver if account_ver is None else int(account_ver)
                chain_ver = current_chain_ver if chain_ver is None else int(chain_ver)

            # Refresh tokens are single-use: claim_jti_for_rotation atomically
            # marks this jti redeemed only if it wasn't already. A jti found
            # already claimed being presented again means it was replayed:
            # either the legitimate user retried a stale token, two concurrent
            # requests raced on the same token, or the token was stolen and is
            # being used by an attacker in parallel with its rightful owner.
            # Either way, that is reuse, not a routine invalid-token case.
            client_ip = get_client_ip(request) if request is not None else None
            claim = await jwt_service.claim_jti_for_rotation(
                jti,
                payload.get("exp"),
                email,
                client_ip=client_ip,
                account_ver=int(account_ver),
                chain_ver=int(chain_ver),
            )

            # A same-IP duplicate inside the grace window is likely a browser
            # race. Reject it without triggering reuse revocation, but never
            # issue descendant credentials from a token that already rotated.
            if not claim.claimed:
                if await jwt_service.is_benign_duplicate_rotation(jti, client_ip):
                    logger.info("Duplicate refresh within grace window for jti %s; rejecting retry", jti)
                    return None
                else:
                    await RefreshTokenService._handle_reuse_detected(payload, db, request)
                    return None

            # chain_id carried forward unchanged: this is a continuation of
            # the same login, not a new one, so its version-based identity
            # (and therefore what a future targeted revoke would end) stays
            # intact across the rotation.
            issued_at = claim.consumed_at
            new_access_token = await jwt_service.create_access_token(
                email,
                chain_id,
                issued_at=issued_at,
                account_ver=claim.account_ver,
                chain_ver=claim.chain_ver,
            )
            new_refresh_token = await jwt_service.create_refresh_token(
                email,
                chain_id,
                issued_at=issued_at,
                account_ver=claim.account_ver,
                chain_ver=claim.chain_ver,
            )

            # Best-effort: moves the Manage Sessions row from the old jti
            # (just rotated away above) to the new one, rather than changing
            # create_refresh_token's return shape (see login_service.py's
            # identical comment for why).
            new_payload = await jwt_service.decode_payload(new_refresh_token)
            if not new_payload or not new_payload.get("jti") or not new_payload.get("exp"):
                return None
            # Do not let a refresh racing with logout/reuse detection adopt a
            # newer version written after its parent was validated. Comparing
            # to the parent is essential: checking only that the child is
            # current could mint a valid post-revocation descendant.
            if (
                new_payload.get("account_ver", 0) != claim.account_ver
                or new_payload.get("chain_ver", 0) != claim.chain_ver
                or not await jwt_service.is_current_version(new_payload)
            ):
                return None
            await session_service.rotate_session(
                db, jti, new_payload["jti"], chain_id, new_payload["exp"], email=email, request=request
            )

            return {"access_token": new_access_token, "refresh_token": new_refresh_token}

        except Exception:
            logger.error("Error refreshing token:\n%s", traceback.format_exc())
            return None

    @staticmethod
    async def revoke_all_tokens_for_user(email: str, db: AsyncSession | None = None) -> int:
        """Revoke every token for logout-all, password change, or account removal.

        One account-version bump invalidates all tokens without iterating over
        token ids. The return value is the pre-revoke active session count from
        the best-effort Postgres mirror.

        Raises TokenVersionUnavailableError if the account-version bump
        itself could not be confirmed (Postgres unavailable): the Postgres
        mirror is deliberately left untouched in that case, since marking
        sessions revoked there while the durable Postgres version stayed
        unbumped would make Manage Sessions/audit logs lie about whether
        those tokens are actually dead. Callers must not report success
        when this is raised.
        """
        try:
            active_count = await session_service.count_active_sessions(db, email)

            if not await jwt_service.bump_account_version(email):
                raise TokenVersionUnavailableError(f"Failed to bump account version for {email}")

            await session_service.revoke_all_sessions(db, email)
            await publish_session_revoked(email)

            return active_count

        except TokenVersionUnavailableError:
            raise

        except Exception:
            logger.error("Error revoking all tokens for user %s:\n%s", email, traceback.format_exc())
            return 0

    @staticmethod
    async def revoke_all_tokens_for_user_except_chain(
        email: str, exempt_chain_id: str, db: AsyncSession | None = None
    ) -> int:
        """Revoke all active sessions except one authenticated chain.

        Used after an account-settings password change. The caller must mint
        fresh tokens for exempt_chain_id because bumping the account version
        invalidates every existing token, including the exempted session's old
        tokens.

        Returns the number of revoked sessions, excluding the exempted chain.

        Raises TokenVersionUnavailableError on the same terms as
        revoke_all_tokens_for_user above. The password change itself is a
        separate, unrelated DB write - callers should let that succeed and
        only use this exception to flag that other sessions were not
        actually revoked, rather than blocking the password change on it.
        """
        try:
            active_count = await session_service.count_active_sessions(db, email)

            if not await jwt_service.bump_account_version(email):
                raise TokenVersionUnavailableError(f"Failed to bump account version for {email}")

            await session_service.revoke_all_sessions(db, email, exempt_chain_id=exempt_chain_id)
            await publish_session_revoked(email)

            return max(active_count - 1, 0)

        except TokenVersionUnavailableError:
            raise

        except Exception:
            logger.error(
                "Error revoking all tokens except chain %s for user %s:\n%s",
                exempt_chain_id, email, traceback.format_exc()
            )
            return 0

    @staticmethod
    async def revoke_chain_for_user(email: str, chain_id: str, db: AsyncSession | None = None) -> None:
        """Revoke one token chain by chain_id.

        Manage Sessions uses session_id and goes through session_service.
        Reuse detection only has chain_id, so it comes through here. Other
        chains on the account stay valid.

        Raises TokenVersionUnavailableError if the chain-version bump could
        not be confirmed - see _handle_reuse_detected, this method's only
        caller, for how a security-critical caller must react to that
        rather than treating it as a routine, swallowable failure.
        """
        try:
            if not await jwt_service.bump_chain_version(email, chain_id):
                raise TokenVersionUnavailableError(f"Failed to bump chain version for {email}/{chain_id}")

            await session_service.revoke_chain(db, chain_id)
            await publish_session_revoked(email)

        except TokenVersionUnavailableError:
            raise

        except Exception:
            logger.error(
                "Error revoking chain %s for user %s:\n%s", chain_id, email, traceback.format_exc()
            )

    @staticmethod
    async def _handle_reuse_detected(
        payload: dict, db: AsyncSession | None = None, request: Request | None = None
    ) -> None:
        """
        payload is the already-decoded claims of a refresh token whose jti
        was already claimed (see claim_jti_for_rotation). Accepting it
        directly avoids decoding the token a second time, since the caller
        already did that once to reach this point.

        The reused token itself is always rejected regardless of what
        happens here: refresh_tokens() returns None unconditionally right
        after calling this method (see the "not claimed" branch above), so
        this stays fail-closed for the actual request in flight even if the
        version bump below can't be confirmed. What TokenVersionUnavailableError
        changes is only whether *other* tokens on the account/chain actually
        got invalidated too - caught here (rather than left to propagate)
        so the critical log and audit event, the evidence that theft was
        detected at all, still get written even when Postgres is down.
        """
        email = payload.get("email")

        if not email:
            logger.warning("Refresh token reuse detected, but no email claim was present")
            return

        chain_id = payload.get("chain")
        revocation_confirmed = True
        try:
            if chain_id:
                # Scoped: only the compromised chain (this reused token's
                # own lineage) is revoked. See revoke_chain_for_user.
                await RefreshTokenService.revoke_chain_for_user(email, chain_id, db)
            else:
                # A pre-upgrade token minted with no "chain" claim: lineage
                # is unknown, so fall back to the account-wide,
                # maximally-safe response.
                await RefreshTokenService.revoke_all_tokens_for_user(email, db)
        except TokenVersionUnavailableError:
            revocation_confirmed = False

        revoked_description = f"chain {chain_id}" if chain_id else "the whole account (no chain claim)"

        # Logged at a severity that stands out from routine single-token
        # revocations, since this indicates likely token theft rather than an
        # expected rotation.
        if revocation_confirmed:
            logger.critical("Refresh token reuse detected for %s, revoked %s", email, revoked_description)
        else:
            logger.critical(
                "Refresh token reuse detected for %s, but revocation of %s could not be confirmed "
                "(Postgres unavailable) - those tokens may remain valid until Postgres recovers",
                email, revoked_description,
            )

        metadata: dict[str, str | bool] = {"chain_id": chain_id} if chain_id else {"scope": "account"}
        metadata["revocation_confirmed"] = revocation_confirmed

        await log_security_event(
            REFRESH_TOKEN_REUSE_DETECTED,
            db,
            user_email=email,
            success=False,
            request=request,
            metadata=metadata,
        )
        await capture_security_alert(REFRESH_TOKEN_REUSE_DETECTED, metadata=metadata)


refresh_token_service = RefreshTokenService()
