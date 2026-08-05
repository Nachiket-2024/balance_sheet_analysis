# tests/backend/mystic_auth/unit/emails/test_email_normalization_unit.py
from backend.mystic_auth.emails.email_normalization import normalize_email


def test_normalize_email_lowercases():
    assert normalize_email("User@Example.com") == "user@example.com"


def test_normalize_email_strips_surrounding_whitespace():
    assert normalize_email("  user@example.com  ") == "user@example.com"


def test_normalize_email_is_idempotent():
    once = normalize_email("User@Example.com")
    twice = normalize_email(once)

    assert once == twice
