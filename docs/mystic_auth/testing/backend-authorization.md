# Backend Authorization Test Detail
---

*New to a term here? See the [Testing Glossary](../glossary/testing.md).*

This page is the detailed scenario map for PBAC. It explains the difference
between route-input validation, authorization decisions, persisted grants,
policy mutation safety, and cache/concurrency behavior. A successful test in
one group does not imply the other groups passed.

The source paths are relative to the repository root. Function names are
included where they express a distinct security or data-integrity claim.

---

## Authorization endpoint input and output

### `tests/backend/mystic_auth/unit/api/pbac_routes/test_batch_authorization_route_unit.py`

This isolates the batch-check route from the authorization service. It rejects
an empty batch, rejects a batch above the configured maximum, accepts a batch
at the exact maximum, and rejects checks with a missing action, an empty action,
or the wrong action type. The mocked route tests then verify that trusted
request context is built once, checks are delegated in order, mixed allow/deny
results preserve order, and rejected or failed conditions are not exposed in
the public response.

### `tests/backend/mystic_auth/unit/api/pbac_routes/test_permission_routes_condition_validation_unit.py`

`test_grant_permission_rejects_invalid_conditions_before_touching_repository`
proves malformed condition data is rejected before persistence. The valid-case
test proves a structurally valid condition reaches the repository. The legacy
read test verifies oversized stored conditions are sanitized rather than
returned unbounded to a caller.

### `tests/backend/mystic_auth/unit/api/pbac_routes/test_policy_routes_condition_validation_unit.py`

The create and update cases cover invalid schemas, unknown condition keys, and
valid conditions. The update cases distinguish a condition change from an
unchanged condition, reject deactivation of a baseline policy, allow its
reactivation, and reject clearing conditions to null when the caller is
conditional. These tests prove validation order and baseline protection, not
database transaction behavior.

### `tests/backend/mystic_auth/unit/authorization/test_permission_catalog_schema_unit.py`

Verifies the catalog's permission/action/resource metadata has the required
shape and remains serializable for API consumers.

### `tests/backend/mystic_auth/unit/authorization/test_policy_schema_unit.py`

Verifies policy input/output schemas, required fields, action definitions,
condition representation, and validation errors independently of route code.

---

## Grant authority and protected principals

### `tests/backend/mystic_auth/unit/api/pbac_routes/test_permission_assignment_system_user_guard_unit.py`

The grant and revoke cases prove a route cannot add or remove direct
permissions on the protected system user. The test isolates the guard so a
future repository refactor cannot accidentally move protection after the
write.

### `tests/backend/mystic_auth/unit/api/pbac_routes/test_policy_assignment_system_user_guard_unit.py`

The assignment, removal, and action-revoke cases apply the same protected-user
rule to policy rows and policy actions. This is why `system_superuser` is not
used as an ordinary seeded matrix policy.

### `tests/backend/mystic_auth/unit/api/pbac_routes/test_bulk_system_user_guard_unit.py`

Bulk direct-permission and bulk-policy tests prove only the system-user item is
rejected while other selected users still proceed. Invalid conditions are
rejected before repository writes. This establishes best-effort isolation:
one protected target does not silently authorize or abort unrelated targets.

### `tests/backend/mystic_auth/unit/api/pbac_routes/test_bulk_policy_routes_unit.py`

The bulk-removal cases protect the last holder of the bootstrap superuser
policy, allow removal when another holder remains, avoid incrementing a
lockout counter for a non-holder, and confirm non-superuser policies do not
receive the superuser-only guard.

### `tests/backend/mystic_auth/unit/api/pbac_routes/test_policy_assignment_authorization_security_unit.py`

The cases cover self-escalation to the superuser policy, assigning when the
caller holds every action, rejecting an unheld business-domain policy, and
removing or revoking actions when the caller lacks the current actions. They
also cover the last-superuser-holder guard, the valid-other-holder case,
action-not-in-policy rejection, and the missing-user-policy 404.

### `tests/backend/mystic_auth/unit/api/pbac_routes/test_policy_crud_authorization_security_unit.py`

This file tests grantability at policy CRUD boundaries. It covers minting an
action the caller lacks, requiring all actions for create, allowing non-grant
metadata changes without an unnecessary grant check, protecting baseline
renames/deletes, requiring deactivation before delete, and allowing ordinary
non-baseline deletion when the caller has the current actions. The system
superuser bootstrap case is deliberately the explicit exception.

---

## Policy history and mutation audit

### `tests/backend/mystic_auth/unit/api/pbac_routes/test_policy_history_unit.py`

Creation, update, rollback, and deletion each need a history record with the
right operation and snapshot. The definition-snapshot cases ensure only
definitional fields are compared. Diff tests cover matching policy names and
reject mismatched names. Rollback tests restore live and deleted definitions,
label the new history operation, and reject entries belonging to another
policy. Fallback tests define whether an entry uses its own definition or the
previous one when a deleted entry has no current definition.

### `tests/backend/mystic_auth/unit/authorization/services/test_authorization_audit_logger_unit.py`

Verifies the authorization decision audit record contains actor, action,
resource, result, and safe reason data without recording sensitive condition
internals.

### `tests/backend/mystic_auth/unit/authorization/services/test_authorization_service_audit_log_unit.py`

Verifies policy/direct-grant authorization mutations emit the expected audit
events and do not emit misleading success records when a mutation is denied.

---

## Authorization evaluation internals

- `tests/backend/mystic_auth/unit/authorization/evaluators/test_authorization_decision_unit.py`
  verifies normalized allow/deny objects, public explanations, and failure
  defaults.
- `test_policy_evaluator_unit.py` verifies candidate policy matching, action
  precedence, direct grants, and effective allow/deny outcomes.
- `test_policy_evaluator_detailed_unit.py` verifies the detailed matched,
  rejected, and failed-condition explanations used by audit/debug responses.
- `tests/backend/mystic_auth/unit/authorization/conditions/test_condition_validator_unit.py`
  verifies condition operator/type/required-field validation.
- `test_policy_conditions_unit.py` verifies common condition evaluation and
  fail-closed behavior for unsupported input.
- `test_policy_conditions_network_security_unit.py` verifies IP/network and
  security-related condition decisions.
- `test_policy_conditions_temporal_unit.py` verifies time-window and temporal
  boundary decisions.
- `test_condition_schema_consistency_unit.py` verifies condition schemas stay
  aligned with catalog definitions.
- `tests/backend/mystic_auth/unit/authorization/context/test_request_context_builder_unit.py`
  verifies only trusted request, identity, resource, network, and time values
  enter evaluation context.
- `tests/backend/mystic_auth/unit/authorization/dependencies/test_authorization_dependency_unit.py`
  verifies route dependency wiring, identity requirements, and fail-closed
  denial.

---

## Authorization services, repositories, and cache

- `authorization/services/test_authorization_service_unit.py` verifies the
  main single-check orchestration, dependency failures, and fail-closed output.
- `test_authorization_service_batch_unit.py` verifies ordered independent
  batch decisions and mixed results.
- `test_authorization_service_direct_grants_unit.py` verifies direct grant and
  revoke orchestration, including conditions.
- `test_authorization_grant_guard_context_unit.py` verifies the trusted context
  used to decide whether a caller may grant a requested action.
- `test_bulk_notification_unit.py` verifies per-item bulk result aggregation
  and notification behavior when some items fail.
- `authorization/repositories/test_policy_query_repository_unit.py` verifies
  active/inactive policy queries, filters, and effective-policy lookup.
- `test_policy_repository_caching_unit.py` verifies policy repository cache
  reads, writes, and invalidation hooks.
- `test_user_permission_repository_unit.py` verifies direct-grant retrieval,
  condition data, and effective user permission assembly.
- `authorization/caching/test_authorization_cache_service_unit.py` verifies
  deterministic keys, cache hit/miss behavior, invalidation, and safe behavior
  when Valkey is unavailable.

---

## Persisted PBAC integration scenarios

- `tests/backend/mystic_auth/integration/authorization/test_authorization_check_integration.py`
  verifies an allowed decision names its granting policy, a denial has no
  candidate, and a conditional candidate is distinguished from a granting
  policy when its condition fails.
- `test_policy_assignment_integration.py` verifies assigning/removing a policy
  changes real access, missing assignments return 404, list endpoints expose
  current holders, and self-policy reads work without `policies:read` or being
  shadowed by the management route.
- `test_permission_assignment_integration.py` verifies direct grant/revoke,
  `/auth/me` effective permissions, missing-grant 404s, in-place condition
  updates, list endpoints, and self-permission reads without
  `permissions:read`.
- `test_policy_action_revocation_integration.py` verifies revoking one action
  preserves other actions, does not affect other holders, rejects absent
  actions, preserves unrelated direct grants, and reports missing assignments.
- `test_policy_action_separation_integration.py` gives a caller exactly one of
  read/create/update/delete/assign/revoke and verifies every other policy
  action is denied. This is the action-level least-privilege matrix.
- `test_context_based_authorization_integration.py` verifies corporate-IP
  allow/deny, missing client context denial, business-hour allow/deny, and
  fail-closed behavior with no context.
- `test_authorization_cache_invalidation_integration.py` populates decisions,
  narrows policy actions, deactivates a policy, and revokes a direct grant;
  each mutation must flip the already-cached result.
- `test_purge_cache_invalidation_integration.py` verifies purge removes the
  actual Valkey keys and a new signup using the purged email starts with no
  effective permissions.

---

## Catalog, bulk operations, CRUD, and concurrency

- `test_permission_catalog_integration.py` verifies catalog visibility with
  `permissions:read`, denial without it, the special policy-create/update
  cases, direct grant access, and denial for unrelated actions.
- `test_permission_catalog_usage_integration.py` verifies usage for every
  catalog action, access denial rules, and counts for one policy versus one
  direct grant.
- `test_bulk_permission_assignment_integration.py` verifies all-selected
  grants/removals, already-held and not-held result statuses, condition-change
  regrant semantics, and continuation after one item fails.
- `test_bulk_policy_assignment_integration.py` verifies all-selected policy
  changes, best-effort partial failure, duplicate assignment reporting,
  missing-policy continuation, concurrent duplicate assignment, removals, and
  the caller's own escalation guard.
- `test_bulk_role_assignment_integration.py` verifies role changes for every
  selected user, system/self target protection, invalid-role reporting, and
  continuation for unaffected users.
- `test_policy_crud_integration.py` verifies unauthenticated and ordinary-user
  denial, policy-read requirements, limit handling, system-user CRUD, duplicate
  names, broadening-condition rejection, and rename conflicts.
- `test_policy_list_integration.py` verifies case-insensitive search, exact
  resource/action filters, active filter, sort fallback, and total counts that
  represent the filtered collection rather than one page.
- `test_policy_concurrency_integration.py` verifies concurrent updates do not
  lose writes or corrupt history, update/delete races return 404 rather than
  500, and concurrent bulk removals cannot strip every superuser holder.

---

## Security regression files

- `security/test_batch_authorization_abuse_security.py` verifies batch limits
  cannot be used for request amplification.
- `security/test_context_spoofing_security.py` verifies forged request or
  resource context cannot turn a denial into an allow.
- `security/test_invalid_condition_payload_security.py` verifies unsafe
  condition payloads fail closed before evaluation or persistence.
- `security/test_permission_grant_escalation_security.py` verifies callers
  cannot grant actions they do not hold.
- `security/test_policy_tampering_security.py` verifies protected/default
  policy definitions cannot be altered through unauthorized paths.
- `security/test_privilege_escalation_security.py` verifies role, policy, and
  direct-grant combinations cannot promote an ordinary user.
- `security/test_least_privilege_db_role.py` verifies the restricted database
  role cannot perform operations outside its deployment contract when enabled.

---

## What this page does not prove

These backend scenarios do not prove that a React control is visible or
hidden. That is covered by [Frontend Authorization Test Detail](frontend-authorization.md)
and the browser matrix. They also do not prove the 2026-09-25 real-account
seed mapping; that is documented in [Frontend Browser E2E Tests](frontend-e2e.md)
and `local-scripts/mystic_auth/seed-user-permission-matrix.py`.

---

## See also

- [Backend Test Map](backend.md)
- [Backend Unit Tests](backend-unit.md)
- [Backend Integration Tests](backend-integration.md)
- [Frontend Authorization Test Detail](frontend-authorization.md)
- [Testing Overview](overview.md)
