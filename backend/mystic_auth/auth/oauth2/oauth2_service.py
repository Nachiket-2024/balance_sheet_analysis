import asyncio
import base64

# Hashlib/base64 are used to derive a PKCE code_challenge (SHA256 + base64url) from
# the code_verifier, per RFC 7636 / OAuth 2.1's S256 method.
import hashlib
import secrets
import traceback
from typing import cast

import httpx

from ...authorization.policies.default_policies import SELF_SERVICE_POLICY_NAME

# PBAC: new users get their access via an explicit default policy assignment,
# never via their (metadata-only) role, see claude.md's "Roles" section: "New
# users must receive access through default policy assignment, not default
# roles." Mirrors signup_service.py.
from ...authorization.repositories.policy_repository import policy_repository
from ...emails.email_normalization import normalize_email
from ...logging.logging_config import get_logger
from ...redis.client import redis_client
from ...user_crud.user_crud_collector import user_crud

# UserRole is used ONLY to block OAuth2 login into the reserved system account
# (see login_or_create_user below), mirroring the same guard user_routes.py
# applies to update/delete/role-change. Never used to grant access.
from ...user_table.user_model import UserRole
from ..token_logic.jwt_service import jwt_service

logger = get_logger(__name__)

# Lifetime of an OAuth2 CSRF state token: long enough to cover the user
# completing the Google consent screen, short enough to limit replay risk.
OAUTH2_STATE_TTL_SECONDS = 300


class OAuth2Service:
    @staticmethod
    async def generate_and_store_state() -> tuple[str, str]:
        """
        Issues a single-use CSRF state token plus a PKCE code_challenge for an
        OAuth2 login attempt, returning (state, code_challenge) to embed in the
        Google authorization URL. The code_verifier itself never leaves the server;
        it is persisted in Redis keyed by state, with a short expiry, so the
        callback can retrieve it and the pair can only be redeemed once.

        OAuth 2.1 requires PKCE for every client, confidential or not: it defends
        against authorization-code interception independently of (and in addition
        to) the client_secret and the state check, which only cover CSRF/session
        fixation, not code theft in transit/at the redirect endpoint.
        """
        state = secrets.token_urlsafe(32)

        code_verifier = secrets.token_urlsafe(64)
        digest = hashlib.sha256(code_verifier.encode("ascii")).digest()
        code_challenge = base64.urlsafe_b64encode(digest).rstrip(b"=").decode("ascii")

        await redis_client.set(f"oauth_state:{state}", code_verifier, ex=OAUTH2_STATE_TTL_SECONDS)

        return state, code_challenge

    @staticmethod
    async def consume_state(state: str) -> str | None:
        """
        Returns the stored PKCE code_verifier for a state token from Google's
        callback, or None if it was missing, unknown, or expired.
        """
        if not state:
            return None

        # Atomically fetch-and-delete so the same state (and its paired
        # code_verifier) can never be redeemed twice. redis-py's stub types
        # getdel() for both raw-bytes and decoded-str responses; this client
        # is constructed with decode_responses=True (see redis/client.py),
        # so the result is always str | None here.
        return cast("str | None", await redis_client.getdel(f"oauth_state:{state}"))

    @staticmethod
    async def exchange_code_for_tokens(
        code: str, client_id: str, client_secret: str, redirect_uri: str, code_verifier: str
    ) -> dict | None:
        """
        code_verifier is the PKCE verifier matching the code_challenge sent in the
        original authorization request; Google rejects the exchange if it doesn't
        match, proving this callback belongs to the same party that started the flow.
        """
        try:
            token_url = "https://oauth2.googleapis.com/token"
            data = {
                "code": code,
                "client_id": client_id,
                "client_secret": client_secret,
                "redirect_uri": redirect_uri,
                "grant_type": "authorization_code",
                "code_verifier": code_verifier,
            }

            async with httpx.AsyncClient() as client:
                resp = await client.post(token_url, data=data)
                resp.raise_for_status()
                return resp.json()

        except Exception:
            logger.error("Error exchanging code for tokens:\n%s", traceback.format_exc())
            return None

    @staticmethod
    async def get_user_info(access_token: str) -> dict | None:
        try:
            userinfo_url = "https://www.googleapis.com/oauth2/v3/userinfo"
            headers = {"Authorization": f"Bearer {access_token}"}

            async with httpx.AsyncClient() as client:
                resp = await client.get(userinfo_url, headers=headers)
                resp.raise_for_status()
                return resp.json()

        except Exception:
            logger.error("Error fetching user info:\n%s", traceback.format_exc())
            return None

    @staticmethod
    async def login_or_create_user(db, user_info: dict) -> dict | None:
        """
        Authenticates an existing user or creates a new one from Google's verified
        profile, returning a fresh access/refresh token pair, or None on failure.

        Session/multi-device tracking is handled entirely inside
        jwt_service.create_refresh_token (the jti-based registry used by
        logout-all and reuse detection); nothing further needs to be persisted
        here. An earlier version additionally wrote each token pair into a
        separate `user_tokens:{email}` Redis list, but nothing ever read that
        list; it was pure dead weight that grew forever (no TTL) and needlessly
        held raw, cleartext bearer tokens in Redis on top of the canonical registry.

        Pre-hijacking note: an unverified account is not proof that whoever
        created it owns the email address: anyone can sign up with any email and
        just never click the verification link. If marking a pre-existing account
        verified here didn't also clear hashed_password, an attacker could
        pre-register the victim's email with a password of their choosing, leave
        it unverified, and silently inherit access the moment the real owner later
        signs in with Google: the account would become verified while the
        attacker's password remained valid, letting them log in as the victim
        indefinitely. Clearing hashed_password severs that password the instant
        Google proves the real owner's identity, so only the legitimate owner (via
        Google, or by setting a fresh password afterwards) can authenticate into
        the account from this point on. A previously *verified* account's password
        is never touched: that password was already proven to belong to this
        email's owner, so Google login there is a pure additional login method,
        not a takeover.
        """
        try:
            # Normalized here since this path never touches a Pydantic schema
            # (user_info is Google's raw JSON response, not a validated model)
            # every other entry point normalizes at its schema boundary.
            raw_email = user_info.get("email")
            if not raw_email:
                logger.error("OAuth2 login rejected: Google user info had no email")
                return None

            email: str = normalize_email(raw_email)
            name = user_info.get("name", "Unknown")

            user = await user_crud.get_by_email(email, db)

            # OAuth2 login trusts Google's email_verified alone: there is no
            # password check at all, so without this guard, anyone who controls a
            # Google account matching whatever email the operator chose for the
            # system account (an arbitrary, operator-picked address; nothing stops
            # it from being a real, Google-verifiable one) could sign in as the
            # system superuser entirely bypassing its password.
            if user and user.role == UserRole.system:
                logger.warning("OAuth2 login rejected for reserved system account: %s", email)
                return None

            if not user:
                user_data = {
                    "name": name,
                    "email": email,
                    "role": UserRole.user,        # Metadata/display only, grants nothing
                    "is_verified": True,           # Google has already confirmed this email
                    "is_active": True,
                    "hashed_password": None,       # No password for OAuth2-only users
                }
                user = await user_crud.create(user_data, db)

                # Assign the baseline self-service policy: the actual source of
                # this account's access, per PBAC (mirrors signup_service.py's
                # password-signup path).
                self_service_policy = await policy_repository.get_by_name(SELF_SERVICE_POLICY_NAME, db)
                if self_service_policy:
                    await policy_repository.assign_policy_to_user(
                        user_id=user.id, policy_id=self_service_policy.id, db=db, assigned_by="system"
                    )
                else:
                    # Should never happen once the seeding migration has run;
                    # logged loudly rather than failing OAuth2 login outright,
                    # since a missing baseline policy is an operational/migration
                    # issue, not something this particular login request caused.
                    logger.error(
                        "Default policy '%s' not found: new OAuth2 user %s created with no assigned policies",
                        SELF_SERVICE_POLICY_NAME, email,
                    )

            # Google's confirmed email_verified is equally valid proof of
            # ownership as clicking our own verification email, so a pre-existing
            # unverified account is verified now. See the pre-hijacking note above
            # for why hashed_password is cleared in the same step.
            elif not user.is_verified:
                updated_user = await user_crud.update_by_email(
                    email, {"is_verified": True, "hashed_password": None}, db
                )
                # Keep the already-fetched user object if the update raced with a
                # deletion; role/email are unaffected either way.
                if updated_user:
                    user = updated_user

            # Mirrors login_service.py's same check for password-based login: a
            # deactivated account's tokens would ultimately be rejected by
            # current_user_handler.py anyway, but this login boundary is the right
            # place to give a clear "account deactivated" outcome instead.
            if not user.is_active:
                logger.info("OAuth2 login blocked for deactivated account: %s", email)
                return None

            access_token, refresh_token = await asyncio.gather(
                jwt_service.create_access_token(email),
                jwt_service.create_refresh_token(email)
            )

            return {"access_token": access_token, "refresh_token": refresh_token}

        except Exception:
            logger.error("Error in login or create user:\n%s", traceback.format_exc())
            return None


oauth2_service = OAuth2Service()
