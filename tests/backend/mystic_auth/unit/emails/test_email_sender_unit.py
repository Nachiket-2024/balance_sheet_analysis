# tests/backend/mystic_auth/unit/emails/test_email_sender_unit.py
#
# SMTPEmailSender was only ever exercised indirectly through
# test_email_tasks_unit.py mocking email_sender.send wholesale; nothing
# asserted on what it actually builds and passes to aiosmtplib.
from unittest.mock import AsyncMock

import pytest

from backend.mystic_auth.emails.email_sender import SMTPEmailSender

MODULE = "backend.mystic_auth.emails.email_sender"


@pytest.mark.asyncio
async def test_send_builds_message_with_settings_driven_headers(mocker):
    send_mock = mocker.patch(f"{MODULE}.aiosmtplib.send", new_callable=AsyncMock)
    mocker.patch(f"{MODULE}.settings.FROM_EMAIL", "from@example.com")
    mocker.patch(f"{MODULE}.settings.SUPPORT_EMAIL", "support@example.com")
    mocker.patch(f"{MODULE}.settings.SMTP_HOST", "smtp.example.com")
    mocker.patch(f"{MODULE}.settings.SMTP_PORT", 2525)
    mocker.patch(f"{MODULE}.settings.GMAIL_APP_PASSWORD", "app-password")

    sender = SMTPEmailSender()
    await sender.send("user@example.com", "Verify your account", "<p>Hi</p>")

    send_mock.assert_awaited_once()
    message, kwargs = send_mock.call_args.args[0], send_mock.call_args.kwargs
    assert message["From"] == "from@example.com"
    assert message["To"] == "user@example.com"
    assert message["Reply-To"] == "support@example.com"
    assert message["Subject"] == "Verify your account"
    assert kwargs == {
        "hostname": "smtp.example.com",
        "port": 2525,
        "start_tls": True,
        "username": "from@example.com",
        "password": "app-password",
    }


@pytest.mark.asyncio
async def test_send_falls_back_to_from_email_when_support_email_unset(mocker):
    send_mock = mocker.patch(f"{MODULE}.aiosmtplib.send", new_callable=AsyncMock)
    mocker.patch(f"{MODULE}.settings.FROM_EMAIL", "from@example.com")
    mocker.patch(f"{MODULE}.settings.SUPPORT_EMAIL", "")

    sender = SMTPEmailSender()
    await sender.send("user@example.com", "Subject", "Body")

    message = send_mock.call_args.args[0]
    assert message["Reply-To"] == "from@example.com"


@pytest.mark.asyncio
async def test_send_defaults_to_html_content_type(mocker):
    send_mock = mocker.patch(f"{MODULE}.aiosmtplib.send", new_callable=AsyncMock)

    sender = SMTPEmailSender()
    await sender.send("user@example.com", "Subject", "<p>Hi</p>")

    message = send_mock.call_args.args[0]
    assert message.get_content_type() == "text/html"


@pytest.mark.asyncio
async def test_send_uses_plain_text_when_requested(mocker):
    send_mock = mocker.patch(f"{MODULE}.aiosmtplib.send", new_callable=AsyncMock)

    sender = SMTPEmailSender()
    await sender.send("user@example.com", "Subject", "Plain body", is_html=False)

    message = send_mock.call_args.args[0]
    assert message.get_content_type() == "text/plain"
