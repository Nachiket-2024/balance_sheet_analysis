import asyncio
import traceback
import uuid
from datetime import UTC, datetime

from fastapi import Request

from ...logging.logging_config import get_logger
from ...user.user_crud_collector import user_crud
from ...user_session.session_service import session_service
from ..password_logic.password_service import password_service
from ..token_logic.jwt_service import jwt_service
from ..token_logic.token_schema import TokenPairResponseSchema

logger = get_logger(__name__)


class LoginService:
    """Authenticates a user and issues an access/refresh token pair."""

    @staticmethod
    async def login(email: str, password: str, db=None, request: Request | None = None) -> TokenPairResponseSchema | None:
        try:
            if not email or not password:
                return None

            user = await user_crud.get_by_email(email, db)

            # Compare against the user's real hash if one exists, otherwise a fixed
            # dummy hash, unconditionally and before any not-found/unverified checks.
            # Argon2 hashing is measurably slow, so skipping it on the "not
            # found"/"unverified" branches would let an attacker distinguish those
            # cases from "wrong password on a real account" by response latency
            # alone, enabling account enumeration despite identical response bodies.
            hash_to_check = user.hashed_password if user and user.hashed_password else password_service.DUMMY_HASH
            password_matches = await password_service.verify_password(password, hash_to_check)

            if not user:
                logger.info("Login attempt with non-existing email: %s", email)
                return None

            if not user.is_verified:
                logger.info("Login blocked for unverified account: %s", email)
                return None

            # A deactivated account's tokens would be rejected by
            # current_user_handler.py on first real use anyway, but issuing them at
            # all here is wasteful and misleading (the client would see "login
            # successful" followed immediately by a 403 on the very next request
            # instead of a clear "account deactivated" at the login boundary itself).
            if not user.is_active:
                logger.info("Login blocked for deactivated account: %s", email)
                return None

            if not password_matches:
                logger.warning("Incorrect password for email: %s", email)
                return None

            if db is not None:
                await user_crud.update(user, {"last_login_at": datetime.now(UTC)}, db)

            # A fresh chain_id: this login shares nothing with any other
            # session on the account, so a future targeted revoke of one
            # never has to guess which sessions are related (see
            # jwt_service.py's own docstring on chain_id).
            chain_id = uuid.uuid4().hex
            access_token, refresh_token = await asyncio.gather(
                jwt_service.create_access_token(email=email, chain_id=chain_id),
                jwt_service.create_refresh_token(email=email, chain_id=chain_id)
            )

            # Best-effort session tracking (Manage Sessions dashboard card):
            # decodes the token just minted above rather than changing
            # create_refresh_token's return shape, which several existing
            # unit tests assert on directly.
            refresh_payload = await jwt_service.decode_payload(refresh_token)
            if refresh_payload and refresh_payload.get("jti") and refresh_payload.get("exp"):
                await session_service.create_session(
                    db, user.id, refresh_payload["jti"], chain_id, refresh_payload["exp"], request, email
                )

            return TokenPairResponseSchema(access_token=access_token, refresh_token=refresh_token)

        except Exception:
            logger.error("Error during login:\n%s", traceback.format_exc())
            return None


login_service = LoginService()
