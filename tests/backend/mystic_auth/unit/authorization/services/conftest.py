# AuthorizationService._get_effective_policies fetches both the user's assigned
# policies and their direct permission grants. Most tests in this directory only
# care about the policy-fetching side, so this autouse fixture stubs the
# direct-grants fetch to "the user holds none" by default. Tests that exercise
# direct grants (test_authorization_service_direct_grants_unit.py) override it.
from unittest.mock import AsyncMock

import pytest

MODULE = "backend.mystic_auth.authorization.services.authorization_service"


@pytest.fixture(autouse=True)
def _no_direct_permission_grants_by_default(mocker):
    mocker.patch(f"{MODULE}.user_permission_repository.get_active_permissions_for_user", new_callable=AsyncMock, return_value=[])
