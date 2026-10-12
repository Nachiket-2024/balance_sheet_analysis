from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, MagicMock

import httpx
import pytest

from backend.app.balance_sheets.analysis_models import (
    AnalysisAlert,
    AnalysisNotificationDelivery,
    AnalysisNotificationPolicy,
    AnalysisNotificationPreference,
)
from backend.app.balance_sheets.analysis_notifications import (
    deliver_webhook,
    get_or_create_policy,
    get_or_create_preference,
    get_or_create_webhook_delivery,
    normalize_recipients,
    notification_recipients,
    queue_alert_deliveries,
    validate_policy,
    webhook_payload,
)


def test_recipients_are_normalized_and_deduplicated():
    assert normalize_recipients([" Finance@example.com ", "finance@example.com", "ops@example.com"]) == [
        "finance@example.com",
        "ops@example.com",
    ]


def test_policy_rejects_invalid_severity_hours_and_addresses():
    with pytest.raises(ValueError, match="minimum_severity"):
        validate_policy(recipients=[], minimum_severity="critical", escalation_after_hours=0, escalation_recipients=[])
    with pytest.raises(ValueError, match="720"):
        validate_policy(recipients=[], minimum_severity="review", escalation_after_hours=721, escalation_recipients=[])
    with pytest.raises(ValueError, match="email addresses"):
        validate_policy(recipients=["not-an-email"], minimum_severity="review", escalation_after_hours=0, escalation_recipients=[])


def test_escalation_recipients_are_added_only_after_the_deadline():
    created_at = datetime.now(UTC) - timedelta(hours=3)
    alert = AnalysisAlert(company_id=1, alert_key="cash", alert_type="cash", severity="review", message="cash", created_at=created_at)
    policy = AnalysisNotificationPolicy(
        company_id=1,
        enabled=True,
        recipients=["owner@example.com"],
        minimum_severity="review",
        escalation_after_hours=2,
        escalation_recipients=["director@example.com"],
    )
    assert notification_recipients(alert, policy, datetime.now(UTC)) == ["director@example.com", "owner@example.com"]


def test_info_alert_is_filtered_by_review_policy():
    alert = AnalysisAlert(company_id=1, alert_key="quality", alert_type="quality", severity="info", message="quality")
    policy = AnalysisNotificationPolicy(company_id=1, enabled=True, recipients=["owner@example.com"], minimum_severity="review")
    assert notification_recipients(alert, policy, datetime.now(UTC)) == []


def test_webhook_payload_contains_alert_context_without_configuration_secret():
    alert = AnalysisAlert(
        company_id=4,
        alert_type="falling_cash",
        alert_key="falling_cash:2024",
        severity="review",
        message="Cash fell",
        years=[2024],
        evidence={"end_value": 10},
    )
    assert webhook_payload(alert) == {
        "event": "analysis.alert",
        "company_id": 4,
        "alert_type": "falling_cash",
        "severity": "review",
        "message": "Cash fell",
        "years": [2024],
        "evidence": {"end_value": 10},
    }


@pytest.mark.asyncio
async def test_webhook_delivery_posts_payload_without_following_redirects(mocker):
    mocker.patch("backend.app.balance_sheets.analysis_notifications.ANALYSIS_ALERT_WEBHOOK_URL", "https://alerts.example.test/hook")
    response = MagicMock()
    client = MagicMock()
    client.post = AsyncMock(return_value=response)
    client.__aenter__ = AsyncMock(return_value=client)
    client.__aexit__ = AsyncMock(return_value=False)
    mocker.patch("backend.app.balance_sheets.analysis_notifications.httpx.AsyncClient", return_value=client)
    alert = AnalysisAlert(company_id=4, alert_type="cash", alert_key="cash:2024", severity="review", message="Cash fell", years=[2024])

    assert await deliver_webhook(alert) is True
    client.post.assert_awaited_once()
    assert client.post.call_args.kwargs["json"]["event"] == "analysis.alert"
    assert client.post.call_args.kwargs["json"]["company_id"] == 4
    assert client.post.call_args.kwargs["json"]["years"] == [2024]


class Result:
    def __init__(self, value=None):
        self.value = value

    def scalar_one_or_none(self):
        return self.value

    def scalars(self):
        return self

    def __iter__(self):
        return iter(self.value or [])


@pytest.mark.asyncio
async def test_get_or_create_policy_and_preference_persist_only_missing_records():
    db = MagicMock()
    db.execute = AsyncMock(side_effect=[Result(None), Result(None)])
    db.commit = AsyncMock()
    db.refresh = AsyncMock()
    db.add = MagicMock()

    policy = await get_or_create_policy(8, db)
    preference = await get_or_create_preference("OWNER@example.com", db)

    assert policy.company_id == 8
    assert policy.recipients == []
    assert policy.escalation_recipients == []
    assert preference.user_email == "OWNER@example.com"
    assert db.add.call_count == 2
    assert db.commit.await_count == 2
    assert db.refresh.await_count == 2


@pytest.mark.asyncio
async def test_get_or_create_returns_existing_records_without_writes():
    policy = AnalysisNotificationPolicy(company_id=8, recipients=["a@example.com"])
    from backend.app.balance_sheets.analysis_models import (
        AnalysisNotificationPreference,
    )

    preference = AnalysisNotificationPreference(user_email="owner@example.com", email_enabled=False)
    db = MagicMock()
    db.execute = AsyncMock(side_effect=[Result(policy), Result(preference)])
    db.add = MagicMock()
    db.commit = AsyncMock()

    assert await get_or_create_policy(8, db) is policy
    assert await get_or_create_preference("owner@example.com", db) is preference
    db.add.assert_not_called()
    db.commit.assert_not_awaited()


@pytest.mark.asyncio
async def test_queue_deliveries_skips_existing_and_opted_out_recipients():
    alert = AnalysisAlert(company_id=8, alert_key="cash:2024", alert_type="cash", severity="review", message="Cash")
    alert.id = 10
    policy = AnalysisNotificationPolicy(
        company_id=8,
        enabled=True,
        recipients=[" owner@example.com ", "optout@example.com", "existing@example.com"],
        minimum_severity="review",
    )
    prior = AnalysisNotificationDelivery(alert_id=10, company_id=8, recipient="existing@example.com")
    opt_out = AnalysisNotificationPreference(user_email="optout@example.com", email_enabled=False)

    db = MagicMock()
    db.execute = AsyncMock(side_effect=[Result([prior]), Result([opt_out])])
    db.add = MagicMock()
    db.flush = AsyncMock()

    queued = await queue_alert_deliveries(alert, policy, db)

    assert [item.recipient for item in queued] == ["owner@example.com"]
    db.add.assert_called_once_with(queued[0])
    db.flush.assert_awaited_once()


@pytest.mark.asyncio
async def test_queue_deliveries_returns_early_for_disabled_policy():
    alert = AnalysisAlert(company_id=8, alert_key="cash", alert_type="cash", severity="review", message="Cash")
    policy = AnalysisNotificationPolicy(company_id=8, enabled=False, recipients=["owner@example.com"])
    db = MagicMock()
    db.execute = AsyncMock()

    assert await queue_alert_deliveries(alert, policy, db) == []
    db.execute.assert_not_awaited()


@pytest.mark.asyncio
async def test_webhook_delivery_is_optional_idempotent_and_handles_http_failures(mocker):
    alert = AnalysisAlert(company_id=8, alert_key="cash", alert_type="cash", severity="review", message="Cash")
    db = MagicMock()
    db.execute = AsyncMock(side_effect=[Result(None), Result("already-created")])
    db.add = MagicMock()
    db.flush = AsyncMock()

    mocker.patch("backend.app.balance_sheets.analysis_notifications.ANALYSIS_ALERT_WEBHOOK_URL", "")
    assert await get_or_create_webhook_delivery(alert, db) is None
    assert await deliver_webhook(alert) is False
    db.execute.assert_not_awaited()

    mocker.patch("backend.app.balance_sheets.analysis_notifications.ANALYSIS_ALERT_WEBHOOK_URL", "https://alerts.example.test/hook")
    created = await get_or_create_webhook_delivery(alert, db)
    assert created.channel == "webhook"
    assert created.recipient == "configured-webhook"
    assert await get_or_create_webhook_delivery(alert, db) == "already-created"
    db.flush.assert_awaited_once()

    response = MagicMock()
    response.raise_for_status.side_effect = httpx.HTTPStatusError("bad status", request=MagicMock(), response=MagicMock())
    client = MagicMock()
    client.post = AsyncMock(return_value=response)
    client.__aenter__ = AsyncMock(return_value=client)
    client.__aexit__ = AsyncMock(return_value=False)
    mocker.patch("backend.app.balance_sheets.analysis_notifications.httpx.AsyncClient", return_value=client)
    assert await deliver_webhook(alert) is False
