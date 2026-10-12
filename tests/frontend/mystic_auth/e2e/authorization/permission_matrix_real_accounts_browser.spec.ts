// Real (non-mocked) counterpart to permission_matrix_browser.spec.ts.
//
// This suite logs in against the real backend as one account per verified and
// active seed bucket. The seed script's status plan makes these 32 buckets
// login-capable; unverified/deactivated copies are covered by backend checks.
// Keep the policy/direct-grant data below derived from a live /auth/me read
// when the seed matrix changes. The test compares sets, so API ordering is not
// part of the contract.
import { expect, test } from "../../../../../frontend/e2e/playwright";
import { API_BASE_URL } from "../support/authenticatedMysticAuthApiRoutes";

const PASSWORD = "MatrixPassw0rd!";

const POLICY_PERMISSIONS: Record<number, string[]> = {
  0: [],
  1: ["users:read_own", "users:update_own"],
  2: [
    "users:read_own",
    "users:update_own",
    "users:list_all",
    "users:update_any",
    "users:deactivate_any",
    "users:assign_role",
  ],
  3: [
    "policies:read",
    "policies:create",
    "policies:update",
    "policies:delete",
    "policies:assign",
    "policies:revoke",
    "rate_limits:read",
    "rate_limits:reset",
  ],
  4: [
    "policies:read",
    "policies:update",
    "policies:revoke",
    "security_audit:read",
    "users:delete_any",
    "users:reactivate",
  ],
};

const DIRECT_PERMISSIONS = [
  [],
  ["users:read_own"],
  ["users:list_all"],
  ["users:read_own", "policies:read"],
];

const effectivePermissions = (policyIndex: number, directIndex: number) => [
  ...new Set([
    ...POLICY_PERMISSIONS[policyIndex],
    ...DIRECT_PERMISSIONS[directIndex],
  ]),
];

const bucket = (role: string, policyIndex: number, directIndex: number) => ({
  email: `matrix-${role}-verified-active-p${policyIndex}-d${directIndex}-copy1@example.com`,
  expectedPermissions: effectivePermissions(policyIndex, directIndex),
});

// ROLES is ordered user, admin in the seed script. Its current status plan
// makes user p0-p4 and admin p0/p3/p4 verified+active.
const BUCKETS = [
  ...[0, 3, 4].flatMap((policyIndex) =>
    DIRECT_PERMISSIONS.map((_, directIndex) =>
      bucket("admin", policyIndex, directIndex),
    ),
  ),
  ...[0, 1, 2, 3, 4].flatMap((policyIndex) =>
    DIRECT_PERMISSIONS.map((_, directIndex) =>
      bucket("user", policyIndex, directIndex),
    ),
  ),
];

const has = (perms: string[], action: string) => perms.includes(action);

test.describe("permission matrix - real seeded accounts, real backend", () => {
  for (const bucket of BUCKETS) {
    test(`${bucket.email} - nav/route/audit-log visibility matches its real DB grants`, async ({
      page,
    }) => {
      const loginResponse = await page.request.post(
        `${API_BASE_URL}/auth/login`,
        { data: { email: bucket.email, password: PASSWORD } },
      );
      test.skip(
        loginResponse.status() === 404,
        "seed matrix not present on this stack - run seed-user-permission-matrix.py first",
      );
      expect(
        loginResponse.status(),
        `login for ${bucket.email} failed unexpectedly (429 here usually means the per-IP ` +
          "rate limiter tripped from running this whole matrix repeatedly in a short window - see MAX_REQUESTS_PER_WINDOW " +
          "in docs/mystic_auth/testing/frontend-e2e.md#authorization-matrix, not a real permission bug)",
      ).toBe(200);

      // page.request and the browser page share a context, but WebKit and
      // Firefox can expose the response before the Set-Cookie commit is
      // observable to a subsequent request. Poll the actual authentication
      // contract instead of sleeping for an arbitrary duration.
      let actualPermissions: string[] = [];
      await expect
        .poll(
          async () => {
            const meResponse = await page.request.get(`${API_BASE_URL}/auth/me`);
            if (meResponse.status() !== 200) return null;
            actualPermissions = (await meResponse.json()).permissions ?? [];
            return actualPermissions;
          },
          {
            message: `/auth/me for ${bucket.email} did not become authenticated after login`,
            intervals: [100, 200, 500],
            timeout: 5_000,
          },
        )
        .not.toBeNull();
      expect(
        new Set(actualPermissions),
        `${bucket.email} DB grants changed since this test was written`,
      ).toEqual(new Set(bucket.expectedPermissions));

      await page.goto("/dashboard");
      await expect(page.locator("main")).toBeVisible();

      const routeExpectations = [
        ["/users", has(actualPermissions, "users:list_all")],
        [
          "/policies",
          has(actualPermissions, "policies:read") ||
            has(actualPermissions, "policies:create"),
        ],
        ["/permissions", has(actualPermissions, "permissions:read")],
        ["/rate-limits", has(actualPermissions, "rate_limits:read")],
      ] as const;

      for (const [path, allowed] of routeExpectations) {
        await page.goto(path);
        if (allowed) {
          await expect(page.locator("main")).toBeVisible();
          await expect(page).not.toHaveURL(/not-authorized/);
        } else {
          await expect(page).toHaveURL(/not-authorized/);
        }
      }

      await page.goto("/audit-log");
      await expect(
        page.getByRole("heading", { name: /audit log/i }),
      ).toBeVisible();
      // Authorization decisions use policies:read. Security Events has its
      // own All users gate, which is the security_audit:read path covered by
      // the p4 buckets.
      await expect(page.getByRole("tab", { name: /all users/i })).toHaveCount(
        has(actualPermissions, "policies:read") ? 1 : 0,
      );
      await page.getByRole("tab", { name: /security events/i }).click();
      await expect(page.getByRole("tab", { name: /all users/i })).toHaveCount(
        has(actualPermissions, "security_audit:read") ? 1 : 0,
      );
    });
  }
});
