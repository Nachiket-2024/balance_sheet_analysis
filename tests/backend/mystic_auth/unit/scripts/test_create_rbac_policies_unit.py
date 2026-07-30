# tests/backend/mystic_auth/unit/test_create_rbac_policies_unit.py
#
# Covers create_rbac_policies.py: an interactive CLI script that seeds one
# unconditioned, RBAC-shaped policy (name "role_<role>", conditions=None) :
# see docs/mystic_auth/authorization/rbac-quickstart.md for the concept.
# Idempotent by name (skips, doesn't overwrite, if the policy already
# exists) and refuses an empty role name or an empty actions list.
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from backend.mystic_auth.scripts.create_rbac_policies import (
    _policy_name_for_role,
    create_rbac_policy,
)

MODULE = "backend.mystic_auth.scripts.create_rbac_policies"


def _patch_db_session(mocker):
    async def _fake_get_session():
        yield object()

    mocker.patch(f"{MODULE}.database.get_session", side_effect=_fake_get_session)


def test_policy_name_for_role_normalizes_spacing_and_case():
    assert _policy_name_for_role("Editor") == "role_editor"
    assert _policy_name_for_role("  Group Exec  ") == "role_group_exec"


@pytest.mark.asyncio
async def test_creates_an_unconditioned_policy_for_a_new_role(mocker):
    _patch_db_session(mocker)
    mocker.patch(f"{MODULE}.policy_repository.get_by_name", new_callable=AsyncMock, return_value=None)
    created = SimpleNamespace(name="role_editor", actions=["documents:view", "documents:edit"])
    create_mock = mocker.patch(f"{MODULE}.policy_repository.create", new_callable=AsyncMock, return_value=created)
    mocker.patch(
        "builtins.input",
        side_effect=["Editor", "documents", "documents:view, documents:edit", ""],
    )

    await create_rbac_policy()

    create_mock.assert_awaited_once()
    data = create_mock.await_args.args[0]
    assert data == {
        "name": "role_editor",
        "description": None,
        "actions": ["documents:view", "documents:edit"],
        "resource_type": "documents",
        "conditions": None,
        "is_active": True,
    }
    assert create_mock.await_args.kwargs["changed_by"] == "system"


@pytest.mark.asyncio
async def test_defaults_resource_type_to_wildcard_when_left_blank(mocker):
    _patch_db_session(mocker)
    mocker.patch(f"{MODULE}.policy_repository.get_by_name", new_callable=AsyncMock, return_value=None)
    created = SimpleNamespace(name="role_viewer", actions=["reports:view"])
    create_mock = mocker.patch(f"{MODULE}.policy_repository.create", new_callable=AsyncMock, return_value=created)
    mocker.patch("builtins.input", side_effect=["viewer", "", "reports:view", "Read-only viewer role"])

    await create_rbac_policy()

    data = create_mock.await_args.args[0]
    assert data["resource_type"] == "*"
    assert data["description"] == "Read-only viewer role"


@pytest.mark.asyncio
async def test_skips_without_changes_when_the_policy_already_exists(mocker):
    _patch_db_session(mocker)
    existing = SimpleNamespace(name="role_editor", actions=["documents:view"])
    mocker.patch(f"{MODULE}.policy_repository.get_by_name", new_callable=AsyncMock, return_value=existing)
    create_mock = mocker.patch(f"{MODULE}.policy_repository.create", new_callable=AsyncMock)
    mocker.patch("builtins.input", side_effect=["Editor", "documents", "documents:view,documents:edit", ""])

    await create_rbac_policy()

    create_mock.assert_not_awaited()


@pytest.mark.asyncio
async def test_aborts_on_an_empty_role_name(mocker):
    create_mock = mocker.patch(f"{MODULE}.policy_repository.create", new_callable=AsyncMock)
    get_by_name_mock = mocker.patch(f"{MODULE}.policy_repository.get_by_name", new_callable=AsyncMock)
    mocker.patch("builtins.input", side_effect=[""])

    await create_rbac_policy()

    create_mock.assert_not_awaited()
    get_by_name_mock.assert_not_awaited()


@pytest.mark.asyncio
async def test_aborts_on_an_empty_actions_list(mocker):
    _patch_db_session(mocker)
    mocker.patch(f"{MODULE}.policy_repository.get_by_name", new_callable=AsyncMock, return_value=None)
    create_mock = mocker.patch(f"{MODULE}.policy_repository.create", new_callable=AsyncMock)
    # Blank actions input, and a stray-comma-only input : both yield an
    # empty actions list after filtering.
    mocker.patch("builtins.input", side_effect=["editor", "documents", " , , "])

    await create_rbac_policy()

    create_mock.assert_not_awaited()
