import type { Page, Route } from "@playwright/test";

export const API_BASE_URL = process.env.E2E_API_BASE_URL ?? "http://localhost:8000";

export const ALL_PERMISSIONS = [
  "users:read_own",
  "users:update_own",
  "users:list_all",
  "users:update_any",
  "users:deactivate_any",
  "users:assign_role",
  "users:assign_system_role",
  "users:delete_any",
  "users:reactivate",
  "policies:read",
  "policies:create",
  "policies:update",
  "policies:delete",
  "policies:assign",
  "policies:revoke",
  "permissions:grant",
  "permissions:revoke",
  "permissions:read",
  "security_audit:read",
  "rate_limits:read",
  "rate_limits:reset",
];

export const systemProfile = {
  name: "Playwright System",
  email: "playwright-system@example.com",
  role: "system",
  permissions: ALL_PERMISSIONS,
  has_password: true,
  created_at: "2026-01-15T00:00:00Z",
  active_sessions: 2,
  brand_color: null,
};

export const leastPrivilegeProfile = {
  name: "Least Privilege",
  email: "least-privilege@example.com",
  role: "user",
  permissions: ["users:read_own", "users:update_own"],
  has_password: true,
  created_at: "2026-02-01T00:00:00Z",
  active_sessions: 1,
  brand_color: null,
};

export const policiesReadOnlyProfile = {
  ...leastPrivilegeProfile,
  name: "Policy Reader",
  email: "policy-reader@example.com",
  permissions: ["policies:read"],
};

export const policiesEditorProfile = {
  ...policiesReadOnlyProfile,
  name: "Policy Editor",
  email: "policy-editor@example.com",
  permissions: ["policies:read", "policies:update"],
};

export const users = [
  {
    id: 1,
    name: "Playwright System",
    email: "playwright-system@example.com",
    role: "system",
    is_verified: true,
    is_active: true,
    created_at: "2026-01-15T00:00:00Z",
    updated_at: "2026-01-15T00:00:00Z",
    deleted_at: null,
    has_password: true,
    brand_color: null,
  },
  {
    id: 2,
    name: "<script>window.__xssUser = true</script>",
    email: "attacker+<script>@example.com",
    role: "user",
    is_verified: false,
    is_active: true,
    created_at: "2026-02-01T00:00:00Z",
    updated_at: "2026-02-01T00:00:00Z",
    deleted_at: null,
    has_password: true,
    brand_color: null,
  },
  {
    id: 3,
    name: "Soft Deleted User",
    email: "deleted@example.com",
    role: "admin",
    is_verified: true,
    is_active: false,
    created_at: "2026-02-02T00:00:00Z",
    updated_at: "2026-02-03T00:00:00Z",
    deleted_at: "2026-02-03T00:00:00Z",
    has_password: true,
    brand_color: null,
  },
];

export const policies = [
  {
    id: 1,
    name: "self_service",
    description: "Basic self-service access",
    actions: ["users:read_own", "users:update_own"],
    resource_type: "users",
    conditions: null,
    is_active: true,
    created_at: "2026-01-01T00:00:00Z",
    updated_at: "2026-01-01T00:00:00Z",
    created_by: "system",
  },
  {
    id: 2,
    name: "policy_admin",
    description: "Manage policies safely",
    actions: ["policies:read", "policies:create", "policies:update"],
    resource_type: "policies",
    conditions: null,
    is_active: true,
    created_at: "2026-01-02T00:00:00Z",
    updated_at: "2026-01-02T00:00:00Z",
    created_by: "system",
  },
];

export const permissionCatalog = [
  { action: "users:read_own", resource_type: "users", description: "Read one's own user profile." },
  { action: "users:update_own", resource_type: "users", description: "Update one's own user profile." },
  { action: "users:list_all", resource_type: "users", description: "List all users." },
  { action: "policies:read", resource_type: "policies", description: "Read and list policies." },
  { action: "policies:create", resource_type: "policies", description: "Create policies." },
  { action: "permissions:read", resource_type: "permissions", description: "Read the permission catalog." },
  { action: "rate_limits:reset", resource_type: "rate_limits", description: "Reset rate-limit counters." },
];

const permissionCatalogUsage = permissionCatalog.map((permission) => ({
  action: permission.action,
  policy_user_count: permission.action === "users:list_all" ? 1 : 0,
  direct_grant_count: permission.action === "users:read_own" ? 1 : 0,
  policies: permission.action === "users:list_all" ? ["system_superuser"] : [],
  total_user_count: permission.action === "users:read_own" || permission.action === "users:list_all" ? 1 : 0,
}));

const authorizationLogs = [
  {
    id: 1,
    user_email: "playwright-system@example.com",
    action: "users:list_all",
    resource_type: "users",
    resource_identifier: null,
    allowed: true,
    candidate_policy_names: ["system_superuser"],
    granting_policy_names: ["system_superuser"],
    failed_conditions: null,
    context: { ip: "127.0.0.1" },
    created_at: "2026-03-01T10:00:00Z",
  },
];

const securityLogs = [
  {
    id: 1,
    user_email: "playwright-system@example.com",
    event_type: "login_success",
    success: true,
    ip_address: "127.0.0.1",
    user_agent: "Playwright",
    request_id: "req-playwright",
    event_metadata: { source: "e2e" },
    created_at: "2026-03-01T10:01:00Z",
  },
];

// Keep the fixture larger than PAGE_SIZE so the drawer's keyboard navigation is tested
// across the server-side page boundary, not only within the first rendered page.
const authorizationLogsForPaging = Array.from({ length: 55 }, (_, index) => ({
  ...authorizationLogs[0],
  id: index + 1,
  created_at: `2026-03-${String(1 + Math.floor(index / 24)).padStart(2, "0")}T${String(index % 24).padStart(2, "0")}:00:00Z`,
}));

const rateLimits = [
  {
    key: "login:ip:127.0.0.1",
    endpoint: "login",
    scope: "ip",
    identifier: "127.0.0.1",
    count: 2,
    limit: 10,
    resets_in_seconds: 120,
  },
  {
    key: "login_lock:email:attacker@example.com",
    endpoint: "login_lock",
    scope: "email",
    identifier: "attacker@example.com",
    count: 5,
    limit: 5,
    resets_in_seconds: 600,
  },
];

export async function installAuthenticatedMysticAuthApiRoutes(page: Page, profile = systemProfile) {
  await page.route(`${API_BASE_URL}/auth/session-events`, (route) => route.abort());
  await page.route(`${API_BASE_URL}/auth/me**`, (route) => fulfillJson(route, profile));
  await page.route(`${API_BASE_URL}/auth/sessions**`, (route) => fulfillJson(route, []));
  await page.route(`${API_BASE_URL}/auth/logout`, (route) => fulfillJson(route, { detail: "Logged out" }));
  await page.route(`${API_BASE_URL}/auth/logout/all`, (route) => fulfillJson(route, { detail: "Logged out" }));
  await page.route(`${API_BASE_URL}/users/export**`, (route) => route.fulfill({ body: "name,email\nPlaywright System,playwright-system@example.com\n", headers: corsHeaders() }));
  await page.route(`${API_BASE_URL}/users/**/policies**`, userPolicyRoute);
  await page.route(`${API_BASE_URL}/users/**/permissions**`, userPermissionRoute);
  await page.route(`${API_BASE_URL}/users/**`, userMutationRoute);
  await page.route(`${API_BASE_URL}/users/**`, userListRoute);
  // Registered after the /users/** catch-alls: Playwright runs the most
  // recently registered matching route first, so registering this earlier
  // let userListRoute answer /users/stats instead.
  await page.route(`${API_BASE_URL}/users/stats`, (route) => fulfillJson(route, { total: 3, verified: 2, unverified: 1, inactive: 1 }));
  await page.route(`${API_BASE_URL}/authorization/permissions/catalog`, (route) => fulfillJson(route, permissionCatalog));
  await page.route(`${API_BASE_URL}/authorization/permissions/catalog/usage`, (route) => fulfillJson(route, permissionCatalogUsage));
  await page.route(`${API_BASE_URL}/authorization/users/me/policies`, (route) => fulfillJson(route, { user_email: profile.email, policies }));
  await page.route(`${API_BASE_URL}/authorization/users/me/permissions`, (route) => fulfillJson(route, { user_email: profile.email, permissions: [] }));
  await page.route(`${API_BASE_URL}/authorization/users/**/policies**`, userPolicyRoute);
  await page.route(`${API_BASE_URL}/authorization/users/**/permissions**`, userPermissionRoute);
  await page.route(`${API_BASE_URL}/authorization/policies/**/history**`, (route) => fulfillJson(route, []));
  await page.route(`${API_BASE_URL}/authorization/policies/**`, policyMutationRoute);
  await page.route(`${API_BASE_URL}/authorization/policies**`, policyListRoute);
  await page.route(`${API_BASE_URL}/authorization/audit-log**`, auditRoute(authorizationLogsForPaging));
  await page.route(`${API_BASE_URL}/audit/security-log**`, auditRoute(securityLogs));
  await page.route(`${API_BASE_URL}/rate-limits/**`, rateLimitMutationRoute);
  await page.route(`${API_BASE_URL}/rate-limits/**`, rateLimitListRoute);
}

function withTotal(route: Route, rows: unknown[], total = rows.length) {
  return fulfillJson(route, rows, { "x-total-count": String(total) });
}

export function corsHeaders(extra?: Record<string, string>) {
  const browserOrigin = new URL(
    process.env.PLAYWRIGHT_BASE_URL ?? "http://localhost:5173",
  ).origin;
  return {
    "access-control-allow-origin": browserOrigin,
    "access-control-allow-credentials": "true",
    "access-control-expose-headers": "x-total-count",
    ...extra,
  };
}

export function fulfillNoContent(route: Route, status = 204) {
  return route.fulfill({ status, headers: corsHeaders() });
}

export function fulfillJson(route: Route, json: unknown, headers?: Record<string, string>, status = 200) {
  return route.fulfill({ status, json, headers: corsHeaders(headers) });
}

function userListRoute(route: Route) {
  if (route.request().method() !== "GET") return route.fallback();
  const url = new URL(route.request().url());
  const search = url.searchParams.get("search")?.toLowerCase() ?? "";
  const role = url.searchParams.get("role");
  const verified = url.searchParams.get("is_verified");
  const status = url.searchParams.get("status");
  const policy = url.searchParams.get("policy");
  const policyHolders: Record<string, number[]> = {
    self_service: [1, 2, 3],
    policy_admin: [1],
  };
  const rows = users.filter((user) => {
    if (search && !`${user.name} ${user.email}`.toLowerCase().includes(search)) return false;
    if (role && user.role !== role) return false;
    if (verified === "true" && !user.is_verified) return false;
    if (verified === "false" && user.is_verified) return false;
    const effectiveStatus = status ?? (verified ? "active" : null);
    if (effectiveStatus === "active" && (!user.is_active || user.deleted_at)) return false;
    if (effectiveStatus === "deleted" && !user.deleted_at) return false;
    if (policy && !policyHolders[policy]?.includes(user.id)) return false;
    return true;
  });
  return withTotal(route, rows, rows.length > 1 ? 52 : rows.length);
}

function userMutationRoute(route: Route) {
  if (route.request().method() === "GET") return route.fallback();
  if (route.request().method() === "PUT" && route.request().url().endsWith("/users/me")) {
    return route.fulfill({ json: { ...users[0], name: "Updated Playwright" } });
  }
  return fulfillJson(route, { detail: "ok" });
}

function userPolicyRoute(route: Route) {
  return fulfillJson(route, { user_email: "attacker+<script>@example.com", policies });
}

function userPermissionRoute(route: Route) {
  return fulfillJson(route, { user_email: "attacker+<script>@example.com", permissions: permissionCatalog.slice(0, 2) });
}

function policyListRoute(route: Route) {
  if (route.request().method() === "GET") return withTotal(route, policies, 51);
  return fulfillJson(route, policies[0]);
}

function policyMutationRoute(route: Route) {
  if (route.request().method() === "GET") return fulfillJson(route, policies[0]);
  return fulfillJson(route, policies[0]);
}

function auditRoute(rows: unknown[]) {
  return (route: Route) => {
    if (route.request().url().includes("login-trend")) {
      return fulfillJson(route, [{ date: "2026-03-01", success: 1, failure: 0 }]);
    }
    const url = new URL(route.request().url());
    const limit = Number(url.searchParams.get("limit") ?? 50);
    const offset = Number(url.searchParams.get("offset") ?? 0);
    return withTotal(route, rows.slice(offset, offset + limit), rows.length);
  };
}

function rateLimitListRoute(route: Route) {
    if (route.request().method() !== "GET") return route.fallback();
    if (route.request().url().endsWith("/rate-limits/summary")) {
        return fulfillJson(route, {
            total: 22,
            at_limit: 4,
            login_lockouts: 1,
            by_endpoint: { login: 10, login_lock: 1 },
            by_scope: { ip: 15, account: 6, email: 1 },
            truncated: false,
        });
    }
    return fulfillJson(route, { entries: rateLimits, total: 22, truncated: false });
}

function rateLimitMutationRoute(route: Route) {
  if (route.request().method() === "GET") return route.fallback();
  return route.fulfill({ status: 204, headers: corsHeaders() });
}
