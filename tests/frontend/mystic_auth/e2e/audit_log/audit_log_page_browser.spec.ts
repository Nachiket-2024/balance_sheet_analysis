import { expect, test } from "../../../../../frontend/e2e/playwright";
import { expectNoAccessibilityViolations } from "../support/axeCheck";
import { expectNoHorizontalOverflow } from "../support/browserLayoutAssertions";
import { installAuthenticatedMysticAuthApiRoutes } from "../support/authenticatedMysticAuthApiRoutes";

async function expectNoAuditTableHorizontalOverflow(page: Parameters<typeof expectNoHorizontalOverflow>[0]) {
  const tableScrollArea = page.locator(".data-table-scroll-area").first();
  await expect(tableScrollArea).toBeVisible();
  const overflow = await tableScrollArea.evaluate((element) => element.scrollWidth > element.clientWidth + 1);
  expect(overflow).toBe(false);
}

test.describe("audit log page browser behavior", () => {
  test.beforeEach(async ({ page }) => {
    await installAuthenticatedMysticAuthApiRoutes(page);
  });

  test("tabs, filters, pagination, and detail visibility work", async ({ page }) => {
    await page.goto("/audit-log");
    await expect(page.getByRole("heading", { name: /audit log/i })).toBeVisible();
    await expect(page.getByText("List all users", { exact: true }).first()).toBeVisible();
    await expect(page.getByRole("button", { name: /next page/i }).first()).toBeEnabled();
    await page.getByRole("button", { name: /filter by action/i }).click();
    await page.getByText("List all users", { exact: true }).last().click();
    const authorizationResultFilter = page.getByRole("group", { name: /filter by result/i }).first();
    await authorizationResultFilter.getByRole("button", { name: /allowed/i }).click();

    await page.getByRole("tab", { name: /all users/i }).click();
    await expect(page.getByText("playwright-system@example.com", { exact: true }).first()).toBeVisible();

    await page.getByRole("tab", { name: /security events/i }).click();
    await expect(page.getByText("Signed in")).toBeVisible();
    const securityResultFilter = page.getByRole("group", { name: /filter by result/i }).last();
    await securityResultFilter.getByRole("button", { name: /success/i }).click();
    await page.getByLabel(/filter by ip address/i).fill("127.0.0.1");
    await expectNoHorizontalOverflow(page);
    await expectNoAuditTableHorizontalOverflow(page);
  });

  test("keyboard navigation crosses the 25-row page boundary in the details drawer", async ({ page }) => {
    await page.goto("/audit-log");
    await page.getByRole("tab", { name: /all users/i }).click();
    await page.getByText("playwright-system@example.com", { exact: true }).first().click();

    const drawer = page.getByRole("dialog");
    await expect(drawer).toBeVisible();
    await expect(drawer).toContainText("1 of 55");

    for (let step = 0; step < 24; step += 1) {
      await page.keyboard.press("ArrowRight");
    }
    await expect(drawer).toContainText("25 of 55");

    await page.keyboard.press("ArrowRight");
    await expect(drawer).toContainText("26 of 55");
  });

  test("has no WCAG 2.1 AA violations in the filters or details drawer", async ({ page }) => {
    await page.goto("/audit-log");
    await expect(page.getByRole("heading", { name: /audit log/i })).toBeVisible();
    await expectNoAccessibilityViolations(page);

    await expect(page.getByRole("button", { name: /filter by action/i })).toBeVisible();
    await expectNoAccessibilityViolations(page);

    await page.getByRole("button", { name: /filter by action/i }).click();
    await page.getByText("List all users", { exact: true }).last().click();
    await page.getByRole("tab", { name: /all users/i }).click();
    await page.getByText("playwright-system@example.com", { exact: true }).first().click();
    await expect(page.getByRole("dialog")).toBeVisible();
    await expectNoAccessibilityViolations(page);
  });

  test("keeps filters, table, and the details drawer usable at 125% and 150% zoom", async ({ page }) => {
    for (const width of [1280, 1440]) {
      await page.setViewportSize({ width, height: 900 });
      await page.goto("/audit-log");
      await expect(page.getByRole("heading", { name: /audit log/i })).toBeVisible();

      for (const zoom of [1.25, 1.5]) {
        await page.evaluate((value) => {
          document.documentElement.style.zoom = String(value);
        }, zoom);

        await expectNoHorizontalOverflow(page);
        await expectNoAuditTableHorizontalOverflow(page);
        await expect(page.getByRole("button", { name: /filter by action/i })).toBeVisible();

        await page.getByText("playwright-system@example.com", { exact: true }).first().click();
        const drawer = page.getByRole("dialog");
        await expect(drawer).toBeVisible();
        const drawerBox = await drawer.boundingBox();
        expect(drawerBox?.width ?? 0, `drawer should remain visible at ${zoom * 100}% zoom`).toBeGreaterThan(0);
        await expectNoHorizontalOverflow(page);
        await expectNoAuditTableHorizontalOverflow(page);
        await page.getByRole("button", { name: /close/i }).first().click();

        await page.evaluate(() => {
          document.documentElement.style.zoom = "";
        });
      }
    }
  });
});
