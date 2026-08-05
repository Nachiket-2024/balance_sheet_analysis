# tests/backend/mystic_auth/unit/test_batch_authorization_route_unit.py
#
# Coverage for POST /authorization/batch-check (the batch
# Authorization API): request validation (empty/oversized/malformed
# batches), that the route builds a real context and delegates to
# AuthorizationService.authorize_batch, and the security requirement that
# a batch response never leaks matched/rejected policies or failed
# conditions.
from unittest.mock import AsyncMock, MagicMock

import pytest
from backend.mystic_auth.api.pbac_routes.authorization_check_routes import batch_check_authorization
from backend.mystic_auth.authorization.evaluators.authorization_decision import AuthorizationDecision
from backend.mystic_auth.authorization.schemas.batch_authorization_schema import (
    MAX_BATCH_SIZE,
    BatchAuthorizationCheckRequest,
)
from pydantic import ValidationError

ROUTES_MODULE = "backend.mystic_auth.api.pbac_routes.authorization_check_routes"

CALLER = {"email": "caller@example.com", "name": "Caller"}


def _request(client_host="203.0.113.7"):
    request = MagicMock()
    request.client.host = client_host
    return request


def _decision(action, resource_type="users", allowed=True, denial_reason=None, **overrides):
    defaults = dict(
        allowed=allowed,
        action=action,
        resource_type=resource_type,
        user="caller@example.com",
        evaluated_policies=["some_policy"],
        matched_policies=["some_policy"] if allowed else [],
        rejected_policies=[] if allowed else ["some_policy"],
        failed_conditions={} if allowed else {"some_policy": ["time"]},
        denial_reason=denial_reason,
        evaluation_timestamp="2026-07-13T12:00:00+00:00",
    )
    defaults.update(overrides)
    return AuthorizationDecision(**defaults)


# ---------------------------- Request validation ----------------------------

def test_empty_batch_is_rejected():
    with pytest.raises(ValidationError):
        BatchAuthorizationCheckRequest(checks=[])


def test_oversized_batch_is_rejected():
    checks = [{"action": "users:read_own", "resource_type": "users"} for _ in range(MAX_BATCH_SIZE + 1)]
    with pytest.raises(ValidationError):
        BatchAuthorizationCheckRequest(checks=checks)


def test_batch_at_max_size_is_accepted():
    checks = [{"action": "users:read_own", "resource_type": "users"} for _ in range(MAX_BATCH_SIZE)]
    BatchAuthorizationCheckRequest(checks=checks)  # must not raise


def test_malformed_check_missing_action_is_rejected():
    with pytest.raises(ValidationError):
        BatchAuthorizationCheckRequest(checks=[{"resource_type": "users"}])


def test_malformed_check_empty_action_string_is_rejected():
    with pytest.raises(ValidationError):
        BatchAuthorizationCheckRequest(checks=[{"action": "", "resource_type": "users"}])


def test_malformed_check_wrong_type_is_rejected():
    with pytest.raises(ValidationError):
        BatchAuthorizationCheckRequest(checks=[{"action": 123, "resource_type": "users"}])


# ---------------------------- Route behavior ----------------------------

@pytest.mark.asyncio
async def test_route_builds_context_and_delegates_to_authorize_batch(mocker):
    batch = BatchAuthorizationCheckRequest(
        checks=[{"action": "documents:view", "resource_type": "documents"}]
    )
    authorize_batch_mock = mocker.patch(
        f"{ROUTES_MODULE}.authorization_service.authorize_batch",
        new_callable=AsyncMock,
        return_value=[_decision("documents:view", "documents", allowed=True)],
    )

    await batch_check_authorization(
        request=_request(client_host="198.51.100.9"), batch=batch, current_user=CALLER, db="fake-db"
    )

    authorize_batch_mock.assert_awaited_once()
    args, kwargs = authorize_batch_mock.await_args
    assert args[0] == "caller@example.com"
    assert args[1] == [{"action": "documents:view", "resource_type": "documents", "resource": None}]
    assert args[2] == "fake-db"
    assert kwargs["context"]["ip_address"] == "198.51.100.9"


@pytest.mark.asyncio
async def test_route_returns_multiple_allowed_checks(mocker):
    batch = BatchAuthorizationCheckRequest(
        checks=[
            {"action": "documents:view", "resource_type": "documents"},
            {"action": "reports:export", "resource_type": "reports"},
        ]
    )
    decisions = [
        _decision("documents:view", "documents", allowed=True),
        _decision("reports:export", "reports", allowed=True),
    ]
    mocker.patch(
        f"{ROUTES_MODULE}.authorization_service.authorize_batch",
        new_callable=AsyncMock,
        return_value=decisions,
    )

    response = await batch_check_authorization(
        request=_request(), batch=batch, current_user=CALLER, db="fake-db"
    )

    assert [r.allowed for r in response.results] == [True, True]


@pytest.mark.asyncio
async def test_route_returns_mixed_allowed_and_denied_checks(mocker):
    batch = BatchAuthorizationCheckRequest(
        checks=[
            {"action": "documents:view", "resource_type": "documents"},
            {"action": "reports:export", "resource_type": "reports"},
        ]
    )
    decisions = [
        _decision("documents:view", "documents", allowed=True),
        _decision("reports:export", "reports", allowed=False, denial_reason="no_matching_policy"),
    ]
    mocker.patch(
        f"{ROUTES_MODULE}.authorization_service.authorize_batch",
        new_callable=AsyncMock,
        return_value=decisions,
    )

    response = await batch_check_authorization(
        request=_request(), batch=batch, current_user=CALLER, db="fake-db"
    )

    assert response.results[0].allowed is True
    assert response.results[0].denial_reason is None
    assert response.results[1].allowed is False
    assert response.results[1].denial_reason == "no_matching_policy"


# ---------------------------- Security: no internal detail leakage ----------------------------

@pytest.mark.asyncio
async def test_batch_response_never_exposes_matched_rejected_or_failed_conditions(mocker):
    """'Do not leak matched policies, rejected policies, or
    failed conditions through normal batch responses.' The response model
    itself has no such fields : this proves the route doesn't smuggle them
    in via extra attributes either."""
    batch = BatchAuthorizationCheckRequest(
        checks=[{"action": "documents:view", "resource_type": "documents"}]
    )
    decision = _decision(
        "documents:view", "documents", allowed=False, denial_reason="condition_failed",
        matched_policies=[], rejected_policies=["secret_policy_name"],
        failed_conditions={"secret_policy_name": ["time"]},
    )
    mocker.patch(
        f"{ROUTES_MODULE}.authorization_service.authorize_batch",
        new_callable=AsyncMock,
        return_value=[decision],
    )

    response = await batch_check_authorization(
        request=_request(), batch=batch, current_user=CALLER, db="fake-db"
    )

    serialized = response.model_dump()
    assert "secret_policy_name" not in str(serialized)
    assert "matched_policies" not in serialized["results"][0]
    assert "rejected_policies" not in serialized["results"][0]
    assert "failed_conditions" not in serialized["results"][0]
    assert set(serialized["results"][0].keys()) == {"action", "resource_type", "allowed", "denial_reason"}
