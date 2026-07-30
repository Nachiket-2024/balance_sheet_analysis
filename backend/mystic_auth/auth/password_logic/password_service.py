import asyncio
from datetime import UTC, datetime, timedelta

import jwt
from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerifyMismatchError

from ...core.settings import settings

_hasher = PasswordHasher()


class PasswordService:
    """Handles password hashing/verification, strength checks, and reset tokens."""

    # A fixed Argon2 hash of an arbitrary, never-used password. Callers that need
    # to perform a password comparison but have no real hash to check against
    # (e.g. login for a nonexistent account, or an OAuth2-only account with
    # hashed_password=None) compare against this instead of skipping the check
    # outright: skipping it would return in a fraction of the time a genuine
    # hash comparison takes, letting a timing attack distinguish "no such
    # account" from "wrong password on a real one". Computed once at import time
    # so it always matches this process's actual Argon2 parameters.
    DUMMY_HASH: str = _hasher.hash("timing-attack-mitigation-placeholder")

    @staticmethod
    async def hash_password(password: str) -> str:
        # Off the event loop: Argon2 is deliberately slow (that's the point), and
        # calling it synchronously inside a coroutine blocks every other
        # concurrent request on this worker for the duration of the hash.
        return await asyncio.to_thread(_hasher.hash, password)

    @staticmethod
    async def verify_password(plain_password: str, hashed_password: str) -> bool:
        # Off the event loop, same rationale as hash_password: this runs on
        # every login attempt (including the DUMMY_HASH timing-mitigation path).
        # argon2-cffi raises on a mismatch (VerifyMismatchError) or a
        # malformed/foreign hash (InvalidHashError) rather than returning
        # False, unlike passlib's `.verify`; normalized to a bool here so
        # callers don't need to know that.
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
        # validly-signed JWT (e.g. an access or refresh token, which carries the
        # same SECRET_KEY signature) that happens to also carry an "email" claim.
        # Role is intentionally excluded: the single users table makes it
        # unnecessary.
        payload: dict[str, str | float] = {
            "email": email,
            "type": "reset",
            "exp": expire.timestamp()
        }

        # Off the event loop, same as jwt_service.py's own encode/decode calls,
        # since PyJWT's encode/decode are sync, so calling them directly here would
        # block every other concurrent request on this worker.
        return await asyncio.to_thread(jwt.encode, payload, settings.SECRET_KEY, settings.JWT_ALGORITHM)

    @staticmethod
    async def verify_reset_token(token: str) -> dict | None:
        try:
            payload = await asyncio.to_thread(
                jwt.decode, token, settings.SECRET_KEY, algorithms=[settings.JWT_ALGORITHM]
            )

            if not payload.get("email"):
                return None

            # Rejects any other validly-signed JWT (e.g. a stolen but
            # still-valid access/refresh token sharing the same SECRET_KEY) that
            # happens to also carry an "email" claim.
            if payload.get("type") != "reset":
                return None

            return payload

        except jwt.ExpiredSignatureError:
            return None

        except jwt.InvalidTokenError:
            return None


password_service = PasswordService()
