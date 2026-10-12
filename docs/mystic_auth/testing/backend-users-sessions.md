# Backend Users and Sessions Test Detail
---

*New to a term here? See the [Testing Glossary](../glossary/testing.md).*

These tests cover user data and lifecycle state after authentication. They
separate self-service permissions from account-management permissions, soft delete
from irreversible purge, and session invalidation from ordinary profile
updates.

---

## User model, schemas, and repositories

- `tests/backend/mystic_auth/unit/user/test_user_model_unit.py` verifies model
  defaults, lifecycle fields, and invariants.
- `unit/user/test_user_schema_unit.py` verifies accepted input, output shape,
  normalization, and validation errors.
- `unit/user/test_user_base_crud_filters_unit.py` verifies scoped filtering,
  status predicates, and safe query construction.
- `unit/user/test_user_base_crud_joins_and_crud_unit.py` verifies joins and
  common create/read/update/delete operations.
- `unit/user/test_user_email_crud_unit.py` verifies normalized email lookup and
  update behavior.
- `unit/user/test_user_role_crud_unit.py` verifies role assignment queries and
  constraints.
- `unit/user/test_user_lifecycle_crud_unit.py` verifies active, deleted, and
  reactivated state mutations.

These unit tests establish repository behavior; the integration files below
prove that route permissions and transaction effects use it correctly.

---

## Self-service profile and password flows

- `integration/user/test_user_self_service_routes_integration.py` verifies
  own-profile update, roleless-user authentication, password change,
  current-password requirements, wrong/same-password rejection, OAuth-only
  first-password behavior, session revocation, current-device preservation,
  Valkey-outage reporting, and profile updates that do not revoke sessions.
- `integration/user/test_user_self_service_account_deletion_integration.py`
  verifies soft deletion, password confirmation, wrong-password rejection,
  system-user protection, session revocation/cookie clearing, OAuth-only
  deletion, confirmation-token deletion, single-use tokens, Valkey persistence,
  garbage tokens, and cross-account token isolation.
- `unit/user_lifecycle/test_user_self_deletion_service_unit.py` isolates the
  self-deletion permission and protected-account decisions.
- `unit/user_lifecycle/test_account_deletion_confirm_handler_unit.py` isolates
  confirmation-token request handling and response states.
- `unit/user_lifecycle/test_account_deletion_service_unit.py` isolates
  soft-delete authorization and state changes.

---

## Permission-protected listing and management

- `integration/user/test_user_list_and_update_integration.py` verifies
  unauthenticated denial, ordinary-user denial, same-role/different-policy
  behavior, policy-derived management capability, roleless policy capability, and
  list limits.
- `integration/user/test_user_admin_listing_integration.py` verifies listing,
  total-count headers, name/email search, role/verification/status filters,
  policy and permission filters, direct-grant holders, and email sorting.
- `integration/user/test_user_admin_management_integration.py` verifies normal
  updates and blocks system-user mutation, deletion, role changes, assigning
  the system role, and self-role changes; it also verifies `admin`-to-`user`
  and `user`-to-`admin` role metadata changes through the role endpoint.
- `integration/user/test_user_account_lifecycle_integration.py` verifies
  system-role assignment, permission-protected soft delete, self-delete protection, deleted
  login denial, active-session revocation, password-change session effects,
  purge permissions and self/system guards, system-user purge, reactivation,
  and reactivation error cases.
- `integration/user/test_user_admin_lifecycle_valkey_outage_integration.py`
  verifies permission-protected password changes report whether session revocation was
  confirmed when Valkey is healthy versus unavailable.

---

## Export, purge, and irreversible cleanup

- `integration/user/test_user_export_integration.py` verifies auth and permission-protected
  permission gates, CSV contents, status filtering/deleted markers, formula
  injection neutralization, and configured maximum result size.
- `integration/user/test_account_purge_task_integration.py` verifies only
  accounts past the grace period are purged, never-deleted accounts are
  ignored, and purged accounts' sessions are revoked.
- `unit/user_lifecycle/test_user_purge_service_unit.py` verifies deletion
  ordering, dependent-data cleanup, and irreversible purge scope.
- `unit/procrastinate_tasks/test_account_purge_tasks_unit.py` verifies task
  scheduling, payloads, retries, and idempotent cleanup.

---

## Session storage and geolocation

- `unit/user_session/test_session_repository_unit.py` verifies session query,
  revoke, cleanup, and current-session protection operations.
- `unit/user_session/test_session_service_unit.py` verifies session lifecycle
  orchestration and revocation results.
- `unit/user_session/test_session_geolocation_unit.py` verifies provider data
  parsing and privacy-safe missing-location fallback.
- `unit/user_session/test_session_events_unit.py` verifies real-time event
  payloads for revocation and permission changes.
- `unit/user_session/test_session_events_failure_unit.py` verifies fail-closed
  lease admission, invalid access tokens, buffered events, publisher failures,
  and cleanup when the stream shuts down unexpectedly.
- `integration/user_session/test_session_geolocation_integration.py` verifies
  city/country persistence when geolocation is available and null fields when
  it is disabled.

---

## See also

- [Backend Test Map](backend.md)
- [Backend Authentication Test Detail](backend-authentication.md)
- [Backend Authorization Test Detail](backend-authorization.md)
- [Backend Integration Tests](backend-integration.md)
- [Testing Overview](overview.md)
