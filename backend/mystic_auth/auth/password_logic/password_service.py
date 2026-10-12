import asyncio
from datetime import UTC, datetime, timedelta

import jwt
from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerifyMismatchError

from ...core.settings import settings
from ..token_logic.jwt_service import jwt_service

_hasher = PasswordHasher()


class PasswordService:
    """Handles password hashing/verification, strength checks, and reset tokens."""

    # A fixed Argon2 hash of a never-used password. Callers with no real
    # hash to check against (nonexistent account, OAuth2-only account)
    # compare against this instead of skipping the check, which would let a
    # timing attack distinguish "no such account" from "wrong password."
    DUMMY_HASH: str = _hasher.hash("timing-attack-mitigation-placeholder")

    @staticmethod
    async def hash_password(password: str) -> str:
        # Off the event loop: Argon2 is deliberately slow (that's the point), and
        # calling it synchronously inside a coroutine blocks every other
        # concurrent request on this worker for the duration of the hash.
        return await asyncio.to_thread(_hasher.hash, password)

    @staticmethod
    async def verify_password(plain_password: str, hashed_password: str) -> bool:
        # argon2-cffi raises on a mismatch or malformed hash rather than
        # returning False; normalized to a bool here so callers don't need
        # to know that.
        try:
            return await asyncio.to_thread(_hasher.verify, hashed_password, plain_password)
        except (VerifyMismatchError, InvalidHashError):
            return False

    @staticmethod
    async def validate_password_strength(password: str) -> bool:
        if len(password) < 8:
            return False

        # Require a mix of character classes: a length-only check accepts
        # passwords like "aaaaaaaa" that are trivially guessable, defeating the
        # point of enforcing a minimum length at all.
        has_upper = any(char.isupper() for char in password)
        has_lower = any(char.islower() for char in password)
        has_digit = any(char.isdigit() for char in password)

        return has_upper and has_lower and has_digit

    @staticmethod
    async def create_reset_token(
        email: str,
        expires_minutes: int = settings.RESET_TOKEN_EXPIRE_MINUTES
    ) -> str:
        expire = datetime.now(UTC) + timedelta(minutes=expires_minutes)

        # The "reset" type claim lets verify_reset_token reject any other
        # validly-signed JWT carrying an "email" claim.
        payload: dict[str, str | float] = {
            "email": email,
            "type": "reset",
            "exp": expire.timestamp(),
            "iss": settings.JWT_ISSUER,
            "aud": settings.JWT_AUDIENCE,
        }

        # Off the event loop, same as jwt_service.py's own encode/decode calls,
        # since PyJWT's encode/decode are sync, so calling them directly here would
        # block every other concurrent request on this worker.
        return await asyncio.to_thread(jwt.encode, payload, settings.SECRET_KEY, settings.JWT_ALGORITHM)

    @staticmethod
    async def verify_reset_token(token: str) -> dict | None:
        try:
            # verify_aud disabled: PyJWT auto-rejects any "aud" claim
            # present at all, which would break tokens minted before that
            # claim existed. has_valid_issuer_and_audience below does the
            # real check with "absent is fine, present-and-wrong is not."
            payload = await asyncio.to_thread(
                jwt.decode,
                token,
                settings.SECRET_KEY,
                algorithms=[settings.JWT_ALGORITHM],
                options={"verify_aud": False},
            )

            if not payload.get("email"):
                return None

            # Rejects any other validly-signed JWT (e.g. a stolen but
            # still-valid access/refresh token sharing the same SECRET_KEY) that
            # happens to also carry an "email" claim.
            if payload.get("type") != "reset":
                return None

            if not jwt_service.has_valid_issuer_and_audience(payload):
                return None

            return payload

        except jwt.ExpiredSignatureError:
            return None

        except jwt.InvalidTokenError:
            return None


password_service = PasswordService()
