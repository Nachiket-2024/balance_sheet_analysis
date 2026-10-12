import { expect, test } from "../../../../../frontend/e2e/playwright";
import { expectNoHorizontalOverflow, expectXssNotExecuted } from "../support/browserLayoutAssertions";
import { installAuthenticatedMysticAuthApiRoutes, leastPrivilegeProfile } from "../support/authenticatedMysticAuthApiRoutes";

test.describe("users page browser behavior", () => {
  test.beforeEach(async ({ page }) => {
    await installAuthenticatedMysticAuthApiRoutes(page);
  });

  test("table, pagination, search, filters, row dialogs, bulk dialogs, and XSS escaping work", async ({ page }) => {
    await page.goto("/users");
    await expect(page.getByRole("heading", { name: /users/i })).toBeVisible();
    await expect(page.getByText("attacker+<script>@example.com", { exact: true })).toBeVisible();
    await expectXssNotExecuted(page);
    await expect(page.getByRole("button", { name: /next page/i }).first()).toBeEnabled();

    await expect(page.locator('select[aria-label="Filter by role"]')).toHaveCount(0);
    await page.getByRole("button", { name: /^Filters/ }).click();

    const searchInput = page.getByPlaceholder(/search by name or email/i);
    await searchInput.fill("<script>alert(1)</script>");
    await expectXssNotExecuted(page);
    await searchInput.fill("");

    await page.getByRole("button", { name: /^view$/i }).nth(1).click();
    await expect(page.getByRole("tab", { name: /Details/ })).toHaveAttribute("aria-selected", "true");
    await page.getByRole("button", { name: "Close", exact: true }).click();

    const attackerRow = page.getByText("attacker+<script>@example.com", { exact: true }).locator("xpath=ancestor::tr");
    await attackerRow.getByRole("button", { name: "Policies" }).click();
    await expect(page.getByRole("tab", { name: /Policies/ })).toHaveAttribute("aria-selected", "true");
    await expect(page.getByRole("dialog")).toBeVisible();
    await page.getByRole("button", { name: "Close", exact: true }).click();

    const userRowCheckbox = page.getByRole("checkbox", { name: /select row/i }).nth(1);
    await userRowCheckbox.focus();
    await page.keyboard.press("Space");
    await expect(userRowCheckbox).toBeChecked();
    for (const action of [/assign \/ revoke policy/i, /grant \/ revoke permission/i, /set role/i]) {
      await page.getByRole("button", { name: action }).click();
      await expect(page.getByRole("dialog")).toBeVisible();
      await page.getByRole("button", { name: /cancel|close/i }).first().click();
    }

    await page.locator('select[aria-label="Filter by role"]').selectOption("user");
    await page.locator('select[aria-label="Filter by verified status"]').selectOption("false");
    await expectNoHorizontalOverflow(page);
  });

  test("stat tile filter shortcuts, and cancel on delete/purge/role-change dialogs, leave state untouched", async ({ page }) => {
    await page.goto("/users");
    await expect(page.getByRole("heading", { name: /users/i })).toBeVisible();

    await page.getByRole("button", { name: /^Filters/ }).click();

    const roleFilter = page.locator('select[aria-label="Filter by role"]');
    const verifiedFilter = page.locator('select[aria-label="Filter by verified status"]');

    // Each stat tile is a filter shortcut (UserStatsCard.tsx): clicking one
    // applies its filter and clears every other one.
    await page.getByRole("button", { name: "Filter users: Verified" }).click();
    await expect(verifiedFilter).toHaveValue("true");

    await page.getByRole("button", { name: "Filter users: Unverified" }).click();
    await expect(verifiedFilter).toHaveValue("false");

    await roleFilter.selectOption("user");
    await page.getByRole("button", { name: "Filter users: Total users" }).click();
    await expect(roleFilter).toHaveValue("");
    await expect(verifiedFilter).toHaveValue("");

    // Delete: cancel must close the dialog without calling DELETE.
    let deleteCalled = false;
    await page.route("**/users/attacker*", (route) => {
      if (route.request().method() === "DELETE") deleteCalled = true;
      route.continue();
    });
    const attackerRow = page.getByText("attacker+<script>@example.com", { exact: true }).locator("xpath=ancestor::tr");
    await attackerRow.getByRole("button", { name: /more actions/i }).click();
    await page.getByRole("menuitem", { name: "Deactivate", exact: true }).click();
    await expect(page.getByRole("heading", { name: "Deactivate user" })).toBeVisible();
    await page.getByRole("button", { name: "Cancel" }).click();
    await expect(page.getByRole("heading", { name: "Deactivate user" })).not.toBeVisible();
    expect(deleteCalled).toBe(false);
    await expect(page.getByText("attacker+<script>@example.com", { exact: true })).toBeVisible();

    // Purge (only offered for the already soft-deleted row): same contract.
    let purgeCalled = false;
    await page.route("**/users/deleted*/purge", (route) => {
      purgeCalled = true;
      route.continue();
    });
    const deletedRow = page.getByText("deleted@example.com", { exact: true }).locator("xpath=ancestor::tr");
    await deletedRow.getByRole("button", { name: /more actions/i }).click();
    await page.getByRole("menuitem", { name: "Delete", exact: true }).click();
    await expect(page.getByRole("heading", { name: "Delete user" })).toBeVisible();
    await page.getByRole("button", { name: "Cancel" }).click();
    await expect(page.getByRole("heading", { name: "Delete user" })).not.toBeVisible();
    expect(purgeCalled).toBe(false);

    // Role change: cancel must leave the trigger showing the original role.
    // Asserted against the visible trigger text, not the accessibility-only
    // hidden native <select> node: Playwright's selectOption() sets that
    // hidden element's DOM value directly, which the real Select component
    // doesn't re-sync from since its own `value` prop (still "user",
    // untouched by cancel) never changes across the cancel - what a real
    // user actually sees is the trigger text below.
    const roleTrigger = page.getByRole("combobox", { name: "Change role for attacker+<script>@example.com" });
    await expect(roleTrigger).toHaveText("User");
    await page.locator('select[aria-label="Change role for attacker+<script>@example.com"]').selectOption("admin");
    await expect(page.getByRole("heading", { name: "Change role" })).toBeVisible();
    await page.getByRole("button", { name: "Cancel" }).click();
    await expect(page.getByRole("heading", { name: "Change role" })).not.toBeVisible();
    await expect(roleTrigger).toHaveText("User");
  });

  test("least-privileged users cannot directly open the users page", async ({ page }) => {
    await installAuthenticatedMysticAuthApiRoutes(page, leastPrivilegeProfile);
    await page.goto("/users");
    await expect(page).toHaveURL(/\/not-authorized$/);
  });

  test("stays within the desktop viewport at common zoom levels", async ({ page }) => {
    for (const width of [1280, 1440]) {
      await page.setViewportSize({ width, height: 900 });
      await page.goto("/users");
      await expect(page.getByRole("heading", { name: /users/i })).toBeVisible();

      for (const zoom of [1.25, 1.5]) {
        await page.evaluate((value) => {
          document.documentElement.style.zoom = String(value);
        }, zoom);
        await expectNoHorizontalOverflow(page);
      }

      await page.evaluate(() => {
        document.documentElement.style.zoom = "";
      });
    }
  });

  test("keeps the access dialog content width stable when tabs have different scroll heights", async ({ page }) => {
    await page.goto("/users");
    const attackerRow = page.getByText("attacker+<script>@example.com", { exact: true }).locator("xpath=ancestor::tr");
    await attackerRow.getByRole("button", { name: "Policies" }).click();

    const dialog = page.getByRole("dialog");
    await expect(dialog).toBeVisible();
    const tabPanel = dialog.locator('[role="tabpanel"]:visible');
    const measure = async () => tabPanel.evaluate((element) => {
      const rect = element.getBoundingClientRect();
      return { left: rect.left, width: rect.width, clientWidth: element.clientWidth };
    });

    await dialog.getByRole("tab", { name: /Details/ }).click();
    const details = await measure();
    await dialog.getByRole("tab", { name: /Policies/ }).click();
    const policies = await measure();
    await dialog.getByRole("tab", { name: /Permissions/ }).click();
    const permissions = await measure();

    for (const current of [policies, permissions]) {
      expect(current.left).toBeCloseTo(details.left, 0);
      expect(current.width).toBeCloseTo(details.width, 0);
      expect(current.clientWidth).toBe(details.clientWidth);
    }
  });

  test("applies policy and verification filters together", async ({ page }) => {
    await page.goto("/users");
    await page.getByRole("button", { name: /^Filters/ }).click();

    await page.getByRole("button", { name: /filter by policy/i }).click();
    await page.getByRole("button", { name: "self_service", exact: true }).click();
    await page.locator('select[aria-label="Filter by verified status"]').selectOption("true");

    await expect(page.getByText("attacker+<script>@example.com", { exact: true })).not.toBeVisible();
    await expect(page.getByText("deleted@example.com", { exact: true })).not.toBeVisible();
    await expect(page.getByRole("table").getByText("Playwright System", { exact: true })).toBeVisible();
  });
});
