import { expect, test } from "../../../../../frontend/e2e/playwright";
import {
  installAuthenticatedMysticAuthApiRoutes,
} from "../support/authenticatedMysticAuthApiRoutes";
import { matrixPermissionProfiles } from "../support/permissionMatrixProfiles";

const has = (profile: { permissions: string[] }, permission: string) => profile.permissions.includes(permission);

test.describe("permission matrix authorization surfaces", () => {
  for (const profile of matrixPermissionProfiles) {
    test(`${profile.name} sees only usable authorization routes and controls`, async ({ page }) => {
      await installAuthenticatedMysticAuthApiRoutes(page, profile);

      const routeExpectations = [
        ["/users", has(profile, "users:list_all")],
        ["/policies", has(profile, "policies:read") || has(profile, "policies:create")],
        ["/permissions", has(profile, "permissions:read")],
        ["/rate-limits", has(profile, "rate_limits:read")],
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
      await expect(page.getByRole("heading", { name: /audit log/i })).toBeVisible();
      await expect(page.getByRole("tab", { name: /all users/i })).toHaveCount(
        has(profile, "policies:read") ? 1 : 0,
      );
      await page.getByRole("tab", { name: /security events/i }).click();
      await expect(page.getByRole("tab", { name: /all users/i })).toHaveCount(
        has(profile, "security_audit:read") ? 1 : 0,
      );
    });

    test(`${profile.name} opens available dialogs and preserves focus on Escape`, async ({ page }) => {
      await installAuthenticatedMysticAuthApiRoutes(page, profile);

      if (has(profile, "users:list_all")) {
        await page.goto("/users");
        const view = page.getByRole("button", { name: /^view$/i }).first();
        await view.click();
        const dialog = page.getByRole("dialog");
        await expect(dialog).toBeVisible();
        await page.keyboard.press("Escape");
        await expect(dialog).toBeHidden();
        await expect(view).toBeFocused();

        const row = page.getByText("attacker+<script>@example.com", { exact: true }).locator("xpath=ancestor::tr");
        if (has(profile, "policies:read")) {
          await row.getByRole("button", { name: "Policies" }).click();
          await expect(page.getByRole("dialog")).toBeVisible();
          await expect(page.getByRole("tab", { name: /details/i })).toHaveCount(1);
          await expect(page.getByRole("tab", { name: /policies/i })).toHaveCount(1);
          await page.keyboard.press("Escape");
        }
      }

      if (has(profile, "policies:read") || has(profile, "policies:create")) {
        await page.goto("/policies");
        const view = page.getByRole("button", { name: /^view$/i }).first();
        await view.click();
        const dialog = page.getByRole("dialog");
        await expect(dialog.getByRole("tab", { name: /details/i })).toBeVisible();
        await expect(dialog.getByRole("tab", { name: /edit/i })).toHaveCount(
          has(profile, "policies:update") ? 1 : 0,
        );
        await page.keyboard.press("Escape");
        await expect(page.locator('button[aria-label="View"]:visible').first()).toBeFocused();
      }

      if (has(profile, "permissions:read")) {
        await page.goto("/permissions");
        await page.getByRole("button", { name: /^Users\b/i }).click();
        const details = page.getByRole("button", { name: /view details/i }).first();
        await details.click();
        await expect(page.getByRole("dialog")).toBeVisible();
        await page.keyboard.press("Escape");
        await expect(details).toBeFocused();
      }

      if (has(profile, "rate_limits:read")) {
        await page.goto("/rate-limits");
        const reset = page.getByRole("button", { name: "Reset", exact: true }).first();
        await reset.click();
        await expect(page.getByRole("alertdialog")).toBeVisible();
        await page.keyboard.press("Escape");
        await expect(reset).toBeFocused();
      }
    });
  }
});
