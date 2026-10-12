import pytest
from pydantic import ValidationError

from backend.mystic_auth.authorization.schemas.bulk_schema import BulkPolicyItem
from backend.mystic_auth.authorization.schemas.policy_schema import (
    POLICY_ACTION_MAX_LENGTH,
    POLICY_DESCRIPTION_MAX_LENGTH,
    POLICY_NAME_MAX_LENGTH,
    POLICY_RESOURCE_TYPE_MAX_LENGTH,
    PolicyCreate,
    PolicyUpdate,
)


def test_policy_descriptions_accept_the_configured_limit():
    description = "x" * POLICY_DESCRIPTION_MAX_LENGTH

    assert PolicyCreate(
        name="short-description",
        description=description,
        actions=["users:read_own"],
        resource_type="users",
    ).description == description
    assert PolicyUpdate(description=description).description == description


@pytest.mark.parametrize(
    "payload",
    [
        {
            "name": "too-long-create",
            "description": "x" * (POLICY_DESCRIPTION_MAX_LENGTH + 1),
            "actions": ["users:read_own"],
            "resource_type": "users",
        },
        {"description": "x" * (POLICY_DESCRIPTION_MAX_LENGTH + 1)},
    ],
)
def test_policy_descriptions_reject_values_over_the_configured_limit(payload):
    schema = PolicyCreate if "name" in payload else PolicyUpdate

    with pytest.raises(ValidationError):
        schema(**payload)


@pytest.mark.parametrize(
    "payload",
    [
        {"name": "", "actions": ["users:read_own"], "resource_type": "users"},
        {"name": "valid", "actions": [], "resource_type": "users"},
        {"name": "valid", "actions": [""], "resource_type": "users"},
        {"name": "valid", "actions": ["x" * (POLICY_ACTION_MAX_LENGTH + 1)], "resource_type": "users"},
        {"name": "valid", "actions": ["users:read_own"], "resource_type": ""},
        {"name": "x" * (POLICY_NAME_MAX_LENGTH + 1), "actions": ["users:read_own"], "resource_type": "users"},
        {"name": "valid", "actions": ["users:read_own"], "resource_type": "x" * (POLICY_RESOURCE_TYPE_MAX_LENGTH + 1)},
    ],
)
def test_policy_create_rejects_empty_or_overlong_authorization_fields(payload):
    with pytest.raises(ValidationError):
        PolicyCreate(**payload)


@pytest.mark.parametrize("actions", [[], [""], ["x" * (POLICY_ACTION_MAX_LENGTH + 1)]])
def test_policy_update_rejects_invalid_action_lists(actions):
    with pytest.raises(ValidationError):
        PolicyUpdate(actions=actions)


@pytest.mark.parametrize("policy_name", ["", "x" * (POLICY_NAME_MAX_LENGTH + 1)])
def test_bulk_policy_assignment_rejects_invalid_policy_names(policy_name):
    with pytest.raises(ValidationError):
        BulkPolicyItem(user_email="admin@example.com", policy_name=policy_name)
