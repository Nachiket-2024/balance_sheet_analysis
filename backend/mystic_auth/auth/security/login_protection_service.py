import traceback

from ...core.settings import settings
from ...logging.logging_config import get_logger
from ...valkey.client import valkey_client

logger = get_logger(__name__)


class LoginProtectionService:
    """Brute-force protection: tracks failed attempts and enforces lockouts in Valkey."""

    MAX_FAILED_LOGIN_ATTEMPTS: int = settings.MAX_FAILED_LOGIN_ATTEMPTS
    LOGIN_LOCKOUT_TIME: int = settings.LOGIN_LOCKOUT_TIME

    # A separate, more lenient threshold than the per-email one above (see
    # settings.py for why): max failed attempts from a single IP across any
    # accounts before that IP is locked out.
    MAX_FAILED_LOGIN_ATTEMPTS_PER_IP: int = settings.MAX_FAILED_LOGIN_ATTEMPTS_PER_IP
    LOGIN_LOCKOUT_TIME_PER_IP: int = settings.LOGIN_LOCKOUT_TIME_PER_IP
    ACTION_RESERVATION_TIME: int = settings.ACTION_RESERVATION_TIME

    @staticmethod
    def _reservation_key(key: str) -> str:
        return f"{key}:inflight"

    @classmethod
    async def begin_protected_action(cls, key: str) -> bool:
        """Atomically reserve a protected one-time action before mutation.

        The ordinary failed-attempt counter is not a mutex: two callers can
        both observe it below the threshold and then mutate the same account.
        A short-lived Valkey SET NX reservation closes that check/mutate race.
        Callers must pair a successful reservation with
        ``finish_protected_action`` in a finally block.
        """
        if await cls.is_locked(key):
            return False

        try:
            reserved = await valkey_client.set(
                cls._reservation_key(key),
                "1",
                ex=cls.ACTION_RESERVATION_TIME,
                nx=True,
            )
            return bool(reserved)
        except Exception:
            logger.error("Error reserving protected action:\n%s", traceback.format_exc())
            return False

    @classmethod
    async def finish_protected_action(cls, key: str, *, success: bool) -> None:
        """Release an action reservation and update its failure counter."""
        try:
            if success:
                await cls.reset_failed_attempts(key)
            else:
                await cls.check_and_record_action(key, success=False)
        finally:
            await cls.release_protected_action(key)

    @classmethod
    async def release_protected_action(cls, key: str) -> None:
        """Release a reservation without changing the failure counter."""

        try:
            await valkey_client.delete(cls._reservation_key(key))
        except Exception:
            logger.error("Error releasing protected action:\n%s", traceback.format_exc())

    @staticmethod
    async def record_failed_attempt(key: str, lockout_time: int = LOGIN_LOCKOUT_TIME) -> None:
        """
        lockout_time defaults to the per-email LOGIN_LOCKOUT_TIME, but callers
        tracking a different dimension (e.g. per-IP) pass their own window so
        the two counters can expire independently.
        """
        try:
            # INCR creates the key at 0 before incrementing if it doesn't already
            # exist, so this needs no separate existence check beforehand. A
            # previous implementation did a GET first purely to decide between
            # SET and INCR, a redundant Valkey round-trip on every failed attempt.
            new_count = await valkey_client.incr(key)

            # Set expiration only the first time the key is created; re-applying
            # it on every later failure would keep sliding the lockout window
            # forward instead of it expiring after the first failure as intended.
            if new_count == 1:
                await valkey_client.expire(key, lockout_time)

        except Exception:
            logger.error("Error recording failed login attempt:\n%s", traceback.format_exc())

    @staticmethod
    async def is_locked(key: str, max_attempts: int = MAX_FAILED_LOGIN_ATTEMPTS) -> bool:
        try:
            count = await valkey_client.get(key)

            return count is not None and int(count) >= max_attempts

        except Exception:
            logger.error("Error checking login lock status:\n%s", traceback.format_exc())
            return True

    @staticmethod
    async def get_remaining_seconds(key: str) -> int:
        """Seconds left until this lockout key naturally expires, floored at
        0. Used to tell a locked-out caller how long to actually wait,
        instead of a bare "try again later" with no timeframe - the same
        thing a `Retry-After` header communicates to a client, just also
        surfaced in the response body for the login form to render.

        0 covers both "key doesn't exist" and "key has no TTL" (valkey TTL's
        -2/-1 respectively): either way there's nothing meaningful left to
        wait out, which can legitimately happen if this races the key
        expiring naturally between the caller's own is_locked check and
        this call.
        """
        try:
            ttl = await valkey_client.ttl(key)
            return max(ttl, 0)

        except Exception:
            logger.error("Error reading lockout TTL:\n%s", traceback.format_exc())
            return 0

    @staticmethod
    async def reset_failed_attempts(key: str) -> None:
        try:
            await valkey_client.delete(key)

        except Exception:
            logger.error("Error resetting failed login attempts:\n%s", traceback.format_exc())

    @staticmethod
    async def check_and_record_action(
        key: str,
        success: bool,
        max_attempts: int = MAX_FAILED_LOGIN_ATTEMPTS,
        lockout_time: int = LOGIN_LOCKOUT_TIME,
    ) -> bool:
        """
        Callers' own is_locked pre-check (e.g. login_handler.py) is just an
        optimization to skip password hashing for an already-locked
        account - not the source of truth. The failure path here is: a
        single atomic Valkey INCR, not a separate is_locked-then-record
        pair, so concurrent failures against the same key can't both read
        "not yet locked" before either increments (that gap let more than
        max_attempts through as 401 under a real burst - see
        test_login_lockout_race_integration.py).
        """
        if success:
            if await LoginProtectionService.is_locked(key, max_attempts):
                return False
            await LoginProtectionService.reset_failed_attempts(key)
            return True

        try:
            new_count = await valkey_client.incr(key)
            if new_count == 1:
                await valkey_client.expire(key, lockout_time)
        except Exception:
            logger.error("Error recording failed login attempt:\n%s", traceback.format_exc())
            return False

        return new_count <= max_attempts


login_protection_service = LoginProtectionService()
