import { expect, test } from "../../../../../frontend/e2e/playwright";
import { fulfillJson, fulfillNoContent, installAuthenticatedMysticAuthApiRoutes } from "../support/authenticatedMysticAuthApiRoutes";

const sessions = [
  {
    id: 1,
    ip_address: "127.0.0.1",
    city: "Sydney",
    country: "Australia",
    user_agent: "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/140.0.0.0 Safari/537.36",
    created_at: "2026-09-20T10:00:00Z",
    last_used_at: "2026-09-24T02:00:00Z",
    is_current: true,
  },
  {
    id: 2,
    ip_address: "203.0.113.8",
    city: "Melbourne",
    country: "Australia",
    user_agent: "Mozilla/5.0 (iPhone; CPU iPhone OS 18_6 like Mac OS X) AppleWebKit/605.1.15 Mobile/15E148 Safari/604.1",
    created_at: "2026-09-21T10:00:00Z",
    last_used_at: "2026-09-23T22:00:00Z",
    is_current: false,
  },
];

test.describe("active sessions browser behavior", () => {
  test.beforeEach(async ({ page }) => {
    await installAuthenticatedMysticAuthApiRoutes(page);
    await page.route("**/auth/sessions", (route) => fulfillJson(route, sessions));
  });

  test("renders both sessions and cancels an end-session dialog with Escape", async ({ page }) => {
    await page.goto("/dashboard");
    const card = page.getByRole("heading", { name: "Active Sessions" }).locator("xpath=ancestor::*[.//table][1]");
    await expect(card).toContainText("This device");
    await expect(card).toContainText("Sydney");
    await expect(card).toContainText("Melbourne");

    const otherSession = card.getByRole("row").filter({ hasText: "Melbourne" });
    const endButton = otherSession.getByRole("button", { name: "Log out" });
    await endButton.click();
    await expect(page.getByRole("alertdialog")).toBeVisible();
    await page.keyboard.press("Escape");
    await expect(page.getByRole("alertdialog")).toBeHidden();
    await expect(endButton).toBeFocused();
  });

  test("confirms a non-current session and reports one successful mutation", async ({ page }) => {
    let deleteCount = 0;
    await page.route("**/auth/sessions/2", async (route) => {
      if (route.request().method() === "DELETE") {
        deleteCount += 1;
        await fulfillNoContent(route);
        return;
      }
      await route.fallback();
    });

    await page.goto("/dashboard");
    const card = page.getByRole("heading", { name: "Active Sessions" }).locator("xpath=ancestor::*[.//table][1]");
    await card.getByRole("row").filter({ hasText: "Melbourne" }).getByRole("button", { name: "Log out" }).click();
    const dialog = page.getByRole("alertdialog");
    await expect(dialog).toContainText("End the session");
    await dialog.getByRole("button", { name: "Log out", exact: true }).click();
    await expect(page.getByText("Session ended")).toBeVisible();
    expect(deleteCount).toBe(1);
  });

  test("select mode, bulk cancel, and log-out-everywhere cancel leave sessions untouched", async ({ page }) => {
    let mutationCount = 0;
    await page.route("**/auth/sessions/**", (route) => {
      if (route.request().method() !== "GET") mutationCount += 1;
      return route.fallback();
    });

    await page.goto("/dashboard");
    const card = page.getByRole("heading", { name: "Active Sessions" }).locator("xpath=ancestor::*[.//table][1]");
    await card.getByRole("button", { name: "Select mode" }).click();
    const otherCheckbox = card.getByRole("checkbox").last();
    await otherCheckbox.check();
    await card.getByRole("button", { name: "Log out selected" }).click();
    await expect(page.getByRole("alertdialog")).toBeVisible();
    await page.getByRole("button", { name: "Cancel", exact: true }).click();
    await expect(page.getByRole("alertdialog")).toBeHidden();

    await card.getByRole("button", { name: "Log out everywhere" }).click();
    await expect(page.getByRole("alertdialog")).toBeVisible();
    await page.keyboard.press("Escape");
    await expect(page.getByRole("alertdialog")).toBeHidden();
    expect(mutationCount).toBe(0);
  });
});
