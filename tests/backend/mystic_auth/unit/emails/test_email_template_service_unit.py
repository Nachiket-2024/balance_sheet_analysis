# tests/backend/mystic_auth/unit/emails/test_email_template_service_unit.py
#
# render_transactional_email backs both verification and password-reset
# emails; nothing directly asserted on what it actually renders.
from backend.mystic_auth.emails.email_template_service import render_transactional_email

MODULE = "backend.mystic_auth.emails.email_template_service"


def test_render_includes_every_caller_supplied_value():
    html = render_transactional_email(
        preheader="Verify your account",
        heading="Verify your email",
        accent_color="#2c3e50",
        intro="Click the button below to verify your account.",
        cta_label="Verify Email",
        cta_url="https://app.example.com/verify?token=abc123",
        expiry_note="This link expires in 24 hours.",
        ignore_note="If you didn't request this, ignore this email.",
    )

    assert "Verify your account" in html
    assert "Verify your email" in html
    assert "Click the button below to verify your account." in html
    assert "Verify Email" in html
    assert "https://app.example.com/verify?token=abc123" in html
    assert "This link expires in 24 hours." in html
    assert "If you didn't request this, ignore this email." in html
    assert "#2c3e50" in html


def test_render_uses_app_name_and_support_email_from_settings(mocker):
    mocker.patch(f"{MODULE}.settings.APP_NAME", "MysticAuth")
    mocker.patch(f"{MODULE}.settings.SUPPORT_EMAIL", "support@example.com")
    mocker.patch(f"{MODULE}.settings.FROM_EMAIL", "from@example.com")

    html = render_transactional_email(
        preheader="p",
        heading="h",
        accent_color="#000000",
        intro="i",
        cta_label="c",
        cta_url="https://example.com",
        expiry_note="e",
        ignore_note="ig",
    )

    assert "MysticAuth" in html
    assert "support@example.com" in html


def test_render_falls_back_to_from_email_when_support_email_unset(mocker):
    mocker.patch(f"{MODULE}.settings.SUPPORT_EMAIL", "")
    mocker.patch(f"{MODULE}.settings.FROM_EMAIL", "from@example.com")

    html = render_transactional_email(
        preheader="p",
        heading="h",
        accent_color="#000000",
        intro="i",
        cta_label="c",
        cta_url="https://example.com",
        expiry_note="e",
        ignore_note="ig",
    )

    assert "mailto:from@example.com" in html


def test_render_produces_well_formed_html_document():
    html = render_transactional_email(
        preheader="p",
        heading="h",
        accent_color="#000000",
        intro="i",
        cta_label="c",
        cta_url="https://example.com",
        expiry_note="e",
        ignore_note="ig",
    )

    assert html.strip().startswith("<!DOCTYPE html>")
    assert html.strip().endswith("</html>")
