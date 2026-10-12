import { expect, test } from "../../../../../frontend/e2e/playwright";
import { installAuthenticatedMysticAuthApiRoutes, permissionCatalog } from "../support/authenticatedMysticAuthApiRoutes";
import { expectNoHorizontalOverflow } from "../support/browserLayoutAssertions";

test.describe("permissions page browser behavior", () => {
  test.beforeEach(async ({ page }) => {
    await installAuthenticatedMysticAuthApiRoutes(page);
  });

  test("list filtering and details dialog work", async ({ page }) => {
    await page.goto("/permissions");
    await page.getByRole("button", { name: /^Users\b/i }).click();
    await expect(page.getByText("Read own users")).toBeVisible();
    await page.getByPlaceholder(/search by action or description/i).fill("policies");
    await page.locator('select[aria-label="Filter by resource type"]').selectOption("policies");
    await page.getByRole("button", { name: /view details/i }).first().click();
    await expect(page.getByRole("dialog")).toBeVisible();
    await expect(page.getByText("Read policies")).toBeVisible();
  });

  test("stays navigable without horizontal overflow at desktop widths and zoom levels", async ({ page }) => {
    for (const width of [1280, 1440]) {
      await page.setViewportSize({ width, height: 900 });
      await page.goto("/permissions");
      await expect(page.getByRole("heading", { name: /permissions/i })).toBeVisible();

      for (const zoom of [1.25, 1.5]) {
        await page.evaluate((value) => {
          document.documentElement.style.zoom = String(value);
        }, zoom);

        await expectNoHorizontalOverflow(page);
        await expect(page.getByPlaceholder(/search by action or description/i)).toBeVisible();
        await expect(page.getByRole("button", { name: /expand all/i })).toBeVisible();
        await expect(page.getByRole("button", { name: /^Users\b/i })).toBeVisible();
      }

      await page.evaluate(() => {
        document.documentElement.style.zoom = "";
      });
    }
  });

  test("keeps the permission details dialog usable with long content at common zoom levels", async ({ page }) => {
    const longDescription = "Read policies and inspect their active policy-holder assignments and direct permission grants without changing authorization state. This description is intentionally long to verify dialog wrapping.";
    const longPolicyName = "policy_with_a_deliberately_long_name_for_dialog_overflow_review";

    await page.route("**/authorization/permissions/catalog", (route) => {
      route.fulfill({
        json: permissionCatalog.map((entry) =>
          entry.action === "policies:read" ? { ...entry, description: longDescription } : entry,
        ),
      });
    });
    await page.route("**/authorization/permissions/catalog/usage", (route) => {
      route.fulfill({
        json: permissionCatalog.map((entry) => ({
          action: entry.action,
          resource_type: entry.resource_type,
          policies: entry.action === "policies:read" ? [{ name: longPolicyName, user_count: 12 }] : [],
          policy_user_count: entry.action === "policies:read" ? 12 : 0,
          direct_grant_count: 0,
          total_user_count: entry.action === "policies:read" ? 12 : 0,
        })),
      });
    });

    for (const width of [1280, 1440]) {
      await page.setViewportSize({ width, height: 900 });
      await page.goto("/permissions");
      await page.getByRole("button", { name: /^Policies\b/i }).click();
      const row = page.getByText("Read policies").locator("xpath=ancestor::tr");
      await row.getByRole("button", { name: /view details/i }).click();

      const dialog = page.getByRole("dialog");
      await expect(dialog).toBeVisible();
      await expect(dialog.getByTitle(longDescription)).toBeVisible();
      await expect(dialog.getByRole("link", { name: new RegExp(`Open policy details for ${longPolicyName}`) })).toBeVisible();

      for (const zoom of [1.25, 1.5]) {
        await page.evaluate((value) => {
          document.documentElement.style.zoom = String(value);
        }, zoom);
        await expectNoHorizontalOverflow(page);

        const bounds = await dialog.boundingBox();
        expect(bounds).not.toBeNull();
        expect(bounds!.x).toBeGreaterThanOrEqual(0);
        expect(bounds!.x + bounds!.width).toBeLessThanOrEqual(width + 1);
      }

      await page.evaluate(() => {
        document.documentElement.style.zoom = "";
      });
      await page.getByRole("button", { name: /^Close$/i }).click();
    }
  });
});
