import { expect, test } from "../../../../../frontend/e2e/playwright";
import {
  fulfillJson,
  corsHeaders,
  installAuthenticatedMysticAuthApiRoutes,
  users,
} from "../support/authenticatedMysticAuthApiRoutes";

const FILTER_SETTLE_BUDGET_MS = process.env.CI ? 2500 : 1600;

test.describe("management responsiveness", () => {
  test.beforeEach(async ({ page }) => {
    await installAuthenticatedMysticAuthApiRoutes(page);
  });

  test("user access dialog shows real content without a blank or large layout jump", async ({ page }) => {
    await page.route("**/users/2/policies", async (route) => {
      await new Promise((resolve) => setTimeout(resolve, 180));
      await fulfillJson(route, { user_email: users[1].email, policies: [] });
    });
    await page.route("**/users/2/permissions", async (route) => {
      await new Promise((resolve) => setTimeout(resolve, 180));
      await fulfillJson(route, { user_email: users[1].email, permissions: [] });
    });

    await page.goto("/users");
    const trigger = page.getByText("attacker+<script>@example.com", { exact: true })
      .locator("xpath=ancestor::tr").getByRole("button", { name: "Policies" });
    const started = await page.evaluate(() => performance.now());
    await trigger.click();
    const dialog = page.getByRole("dialog");
    await expect(dialog).toBeVisible();
    const shellHeight = await dialog.evaluate((element) => element.getBoundingClientRect().height);
    await expect(dialog.getByRole("tab", { name: /policies/i })).toBeVisible();
    await expect(dialog.getByText(/self_service|no policies/i).first()).toBeVisible();
    const loadedAt = await page.evaluate(() => performance.now());
    const loadedHeight = await dialog.evaluate((element) => element.getBoundingClientRect().height);

    // The two mocked access calls are intentionally delayed. Keep enough
    // room for Firefox/WebKit scheduling while still catching a stalled
    // dialog or an unbounded loading state.
    expect(loadedAt - started).toBeLessThan(4000);
    expect(Math.abs(loadedHeight - shellHeight)).toBeLessThan(240);
  });

  test("rapid reset confirmation produces one request and one toast", async ({ page }) => {
    let resets = 0;
    await page.route("**/rate-limits/**", async (route) => {
      if (route.request().method() === "DELETE") resets += 1;
      await route.fallback();
    });
    await page.goto("/rate-limits");
    const reset = page.getByRole("button", { name: "Reset", exact: true }).first();
    await reset.click();
    const confirm = page.getByRole("alertdialog").getByRole("button", { name: /^reset$/i });
    await confirm.dblclick();
    await expect(page.getByText(/rate limit reset/i)).toHaveCount(1);
    expect(resets).toBe(1);
  });

  test("filtering and sorting a 74-row Users dataset settle promptly", async ({ page }) => {
    const largeUsers = Array.from({ length: 74 }, (_, index) => ({
      ...users[index % users.length],
      id: index + 1,
      name: `Matrix User ${String(index + 1).padStart(2, "0")}`,
      email: `matrix-${String(index + 1).padStart(2, "0")}@example.com`,
    }));
    await page.route("**/users/**", (route) => {
      const pathname = new URL(route.request().url()).pathname;
      if (route.request().method() !== "GET" || !["/users", "/users/"].includes(pathname)) {
        return route.fallback();
      }
      const url = new URL(route.request().url());
      const search = url.searchParams.get("search")?.toLowerCase() ?? "";
      const rows = largeUsers.filter((user) => `${user.name} ${user.email}`.toLowerCase().includes(search));
      return route.fulfill({
        json: rows,
        headers: {
          ...corsHeaders(),
          "x-total-count": String(rows.length),
        },
      });
    });
    await page.goto("/users");
    await expect(page.getByText("Matrix User 01", { exact: true })).toBeVisible();

    const search = page.getByPlaceholder(/search by name or email/i);
    const started = await page.evaluate(() => performance.now());
    await search.fill("matrix-74");
    await expect(page.getByText("matrix-74@example.com", { exact: true })).toBeVisible();
    const settled = await page.evaluate(() => performance.now());
    // CI runners share CPU with the rest of the browser matrix. Keep the
    // local budget strict while allowing that known scheduling overhead in
    // CI; this still fails a genuinely stalled filter interaction.
    expect(settled - started).toBeLessThan(FILTER_SETTLE_BUDGET_MS);

    const sortStarted = await page.evaluate(() => performance.now());
    await page.getByRole("columnheader", { name: /name/i }).click();
    await expect(page.getByText("matrix-74@example.com", { exact: true })).toBeVisible();
    const sortSettled = await page.evaluate(() => performance.now());
    expect(sortSettled - sortStarted).toBeLessThan(2500);
  });
});
