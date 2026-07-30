import traceback

from ...core.settings import settings
from ...logging.logging_config import get_logger
from ...redis.client import redis_client

logger = get_logger(__name__)


class LoginProtectionService:
    """Brute-force protection: tracks failed attempts and enforces lockouts in Redis."""

    MAX_FAILED_LOGIN_ATTEMPTS: int = settings.MAX_FAILED_LOGIN_ATTEMPTS
    LOGIN_LOCKOUT_TIME: int = settings.LOGIN_LOCKOUT_TIME

    # A separate, more lenient threshold than the per-email one above (see
    # settings.py for why): max failed attempts from a single IP across any
    # accounts before that IP is locked out.
    MAX_FAILED_LOGIN_ATTEMPTS_PER_IP: int = settings.MAX_FAILED_LOGIN_ATTEMPTS_PER_IP
    LOGIN_LOCKOUT_TIME_PER_IP: int = settings.LOGIN_LOCKOUT_TIME_PER_IP

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
            # SET and INCR, a redundant Redis round-trip on every failed attempt.
            new_count = await redis_client.incr(key)

            # Set expiration only the first time the key is created; re-applying
            # it on every later failure would keep sliding the lockout window
            # forward instead of it expiring after the first failure as intended.
            if new_count == 1:
                await redis_client.expire(key, lockout_time)

        except Exception:
            logger.error("Error recording failed login attempt:\n%s", traceback.format_exc())

    @staticmethod
    async def is_locked(key: str, max_attempts: int = MAX_FAILED_LOGIN_ATTEMPTS) -> bool:
        try:
            count = await redis_client.get(key)

            return count is not None and int(count) >= max_attempts

        except Exception:
            logger.error("Error checking login lock status:\n%s", traceback.format_exc())
            return False

    @staticmethod
    async def reset_failed_attempts(key: str) -> None:
        try:
            await redis_client.delete(key)

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
        The is_locked check here vs. a caller's own pre-check (e.g.
        login_handler.py checks is_locked itself before attempting
        authentication, to skip the password hash comparison entirely for an
        already-locked account) are not redundant despite calling the same
        function. The caller's pre-check answers "should we even try?" before
        any expensive work; this one answers "is the account still unlocked
        right now, after that work finished?", closing the race where a
        concurrent request locks the account in between. Removing either one
        changes behavior: dropping the caller's pre-check means every attempt
        against a locked account still pays for a full password hash
        comparison, and dropping this one lets a login that happens to finish
        just after a concurrent failure crosses the threshold slip through anyway.
        """
        if await LoginProtectionService.is_locked(key, max_attempts):
            return False

        if success:
            await LoginProtectionService.reset_failed_attempts(key)
        else:
            await LoginProtectionService.record_failed_attempt(key, lockout_time)

        return True


login_protection_service = LoginProtectionService()
