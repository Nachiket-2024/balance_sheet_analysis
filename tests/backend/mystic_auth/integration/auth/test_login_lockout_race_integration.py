# tests/backend/mystic_auth/integration/auth/test_login_lockout_race_integration.py
#
# test_login_locks_out_after_max_failed_attempts (test_login_security_
# controls_integration.py) proves the lockout sequentially. This fires the
# same attempts concurrently instead, so a check-then-increment race in the
# Valkey counter (as opposed to genuinely atomic INCR) would actually show up.
import asyncio
from collections import Counter

import pytest

from backend.mystic_auth.core.settings import settings

from .auth_test_accounts import signup_verify_login, unique_email


@pytest.mark.asyncio
async def test_concurrent_failed_logins_lock_out_at_exactly_the_configured_threshold(client, created_emails):
    email = unique_email()
    await signup_verify_login(client, created_emails, email)
    client.cookies.clear()

    attempts = settings.MAX_FAILED_LOGIN_ATTEMPTS + 10
    responses = await asyncio.gather(
        *(client.post("/auth/login", json={"email": email, "password": "wrong-password"}) for _ in range(attempts))
    )

    counts = Counter(resp.status_code for resp in responses)

    # Exactly MAX_FAILED_LOGIN_ATTEMPTS may be evaluated as real credential
    # checks (401 invalid credentials); every other concurrent request must
    # see the lockout (429), not slip through as a 401 the atomic counter
    # should have already closed off.
    assert counts[401] == settings.MAX_FAILED_LOGIN_ATTEMPTS
    assert counts[429] == attempts - settings.MAX_FAILED_LOGIN_ATTEMPTS
    assert counts[401] + counts[429] == attempts
