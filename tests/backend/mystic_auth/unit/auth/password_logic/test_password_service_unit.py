# tests/backend/mystic_auth/unit/test_password_service_unit.py
#
# password_service.py had no dedicated unit coverage despite backing every
# password-based auth flow (signup, reset, timing-attack mitigation). These
# tests pin down hashing/verification round-trips, the strength policy, and
# the fixed dummy hash used to keep login timing constant for nonexistent
# accounts (see login_service.py).
import asyncio
import time

import jwt as pyjwt
import pytest
from backend.mystic_auth.auth.password_logic.password_service import password_service
from backend.mystic_auth.core.settings import settings

# ---------------------------- hash_password / verify_password ----------------------------

@pytest.mark.asyncio
async def test_hash_password_offloads_to_a_thread_instead_of_blocking_the_loop():
    # Regression guard: hash_password must offload Argon2 (slow, CPU-bound)
    # via asyncio.to_thread instead of running it inline. If it ran inline,
    # it would monopolize the event loop and the cheap ticker coroutine
    # couldn't get a turn until the hash finished, so both would appear to
    # finish together instead of the ticker finishing well before the hash.
    ticker_done_at = None
    hash_done_at = None
    start = time.perf_counter()

    async def ticker():
        nonlocal ticker_done_at
        for _ in range(50):
            await asyncio.sleep(0)
        ticker_done_at = time.perf_counter() - start

    async def hasher():
        nonlocal hash_done_at
        await password_service.hash_password("StrongPass123!")
        hash_done_at = time.perf_counter() - start

    await asyncio.gather(ticker(), hasher())

    assert ticker_done_at < hash_done_at * 0.5

@pytest.mark.asyncio
async def test_hash_password_round_trips_with_verify_password():
    hashed = await password_service.hash_password("StrongPass123!")

    assert hashed != "StrongPass123!"
    assert await password_service.verify_password("StrongPass123!", hashed) is True


@pytest.mark.asyncio
async def test_verify_password_rejects_wrong_password():
    hashed = await password_service.hash_password("StrongPass123!")

    assert await password_service.verify_password("WrongPass123!", hashed) is False


@pytest.mark.asyncio
async def test_dummy_hash_is_a_valid_argon2_hash_but_matches_no_real_password():
    # login_service compares against DUMMY_HASH when no real user/hash exists,
    # specifically so that comparison takes the same time as a real one.
    assert await password_service.verify_password("anything", password_service.DUMMY_HASH) is False
    assert await password_service.verify_password(
        "timing-attack-mitigation-placeholder", password_service.DUMMY_HASH
    ) is True


# ---------------------------- validate_password_strength ----------------------------

@pytest.mark.asyncio
async def test_validate_password_strength_rejects_too_short():
    assert await password_service.validate_password_strength("Aa1") is False


@pytest.mark.asyncio
async def test_validate_password_strength_rejects_missing_uppercase():
    assert await password_service.validate_password_strength("lowercase123") is False


@pytest.mark.asyncio
async def test_validate_password_strength_rejects_missing_lowercase():
    assert await password_service.validate_password_strength("UPPERCASE123") is False


@pytest.mark.asyncio
async def test_validate_password_strength_rejects_missing_digit():
    assert await password_service.validate_password_strength("NoDigitsHere") is False


@pytest.mark.asyncio
async def test_validate_password_strength_accepts_mixed_case_and_digit():
    assert await password_service.validate_password_strength("StrongPass123!") is True


# ---------------------------- create_reset_token / verify_reset_token ----------------------------
# Regression guards for the missing "type" claim: previously a reset token's
# JWT payload carried only email + exp, so any other validly-signed JWT with
# an "email" claim (e.g. a stolen but still-valid access/refresh token, which
# shares the same SECRET_KEY) would pass verify_reset_token's checks : the
# Redis single-use record was the only real gate against token-type confusion.

@pytest.mark.asyncio
async def test_reset_token_round_trips_through_create_and_verify():
    token = await password_service.create_reset_token("user@example.com")

    payload = await password_service.verify_reset_token(token)

    assert payload is not None
    assert payload["email"] == "user@example.com"
    assert payload["type"] == "reset"


@pytest.mark.asyncio
async def test_verify_reset_token_rejects_token_missing_type_claim():
    # Simulates a pre-fix token, or any other JWT signed with the same
    # SECRET_KEY that merely happens to carry an "email" claim.
    untyped_token = pyjwt.encode(
        {"email": "user@example.com", "exp": time.time() + 600},
        settings.SECRET_KEY,
        algorithm=settings.JWT_ALGORITHM,
    )

    assert await password_service.verify_reset_token(untyped_token) is None


@pytest.mark.asyncio
async def test_verify_reset_token_rejects_token_with_wrong_type_claim():
    # e.g. a real access token, which shares the same SECRET_KEY/ALGORITHM
    wrong_type_token = pyjwt.encode(
        {"email": "user@example.com", "type": "access", "exp": time.time() + 600},
        settings.SECRET_KEY,
        algorithm=settings.JWT_ALGORITHM,
    )

    assert await password_service.verify_reset_token(wrong_type_token) is None
