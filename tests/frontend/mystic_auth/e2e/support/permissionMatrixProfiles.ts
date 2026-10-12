import { leastPrivilegeProfile } from "./authenticatedMysticAuthApiRoutes";

const matrixProfile = (name: string, permissions: string[]) => ({
  ...leastPrivilegeProfile,
  name,
  email: `${name.toLowerCase().replace(/[^a-z0-9]+/g, "-")}@example.com`,
  permissions,
});

// These are the distinct effective permission sets produced by the seed
// matrix. Role, verification, and active-state variants do not change the
// frontend permission projection, so each is represented once here.
//
// A 2026-09-24 audit session found this list was both incomplete (16 of the
// 24 distinct verified/active role x policy-bundle x direct-grant
// combinations local-scripts/mystic_auth/seed-user-permission-matrix.py actually
// seeds were never represented here at all) and, for the two entries below
// that were meant to model real policy bundles, actually wrong:
// matrix-user-management included users:delete_any/users:reactivate,
// which the real `user_management` policy does not grant, and
// matrix-policy-management was missing rate_limits:read/rate_limits:reset,
// which the real `policy_management` + `rate_limit_management`
// bundle (seed script's third policy_bundle entry) does grant together.
// Both are corrected below against the seed script's own POLICY_BUNDLES/
// DIRECT_PERMISSION_BUNDLES definitions and a live DB read, not guessed.
// The full 24-bucket gap itself is closed by a separate suite that logs in
// as real seeded accounts instead of maintaining a permission list by hand
// here: tests/frontend/mystic_auth/e2e/authorization/permission_matrix_real_accounts_browser.spec.ts.
// Keep this list for the fast mocked-route checks (dialog behavior, focus
// handling) that don't need a live backend; keep the real-account suite as
// the source of truth for "does this permission list match what's actually
// seeded."
export const matrixPermissionProfiles = [
  matrixProfile("matrix-none", ["users:read_own", "users:update_own"]),
  matrixProfile("matrix-list-direct", ["users:read_own", "users:update_own", "users:list_all"]),
  matrixProfile("matrix-user-management", [
    "users:read_own", "users:update_own", "users:list_all", "users:update_any",
    "users:deactivate_any", "users:assign_role",
  ]),
  matrixProfile("matrix-policy-reader", ["users:read_own", "users:update_own", "policies:read"]),
  matrixProfile("matrix-policy-management", [
    "users:read_own", "users:update_own", "policies:read", "policies:create",
    "policies:update", "policies:delete", "policies:assign", "policies:revoke",
    "rate_limits:read", "rate_limits:reset",
  ]),
  matrixProfile("matrix-permission-reader", ["users:read_own", "users:update_own", "permissions:read"]),
  matrixProfile("matrix-rate-limit-management", [
    "users:read_own", "users:update_own", "rate_limits:read", "rate_limits:reset",
  ]),
  matrixProfile("matrix-security-auditor", ["users:read_own", "users:update_own", "security_audit:read"]),
  matrixProfile("matrix-direct-policy-reader", [
    "users:read_own", "users:update_own", "users:list_all", "policies:read",
  ]),
];
