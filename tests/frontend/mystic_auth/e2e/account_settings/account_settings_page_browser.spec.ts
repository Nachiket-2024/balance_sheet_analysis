import { expect, test } from "../../../../../frontend/e2e/playwright";
import { installAuthenticatedMysticAuthApiRoutes } from "../support/authenticatedMysticAuthApiRoutes";

test.describe("account settings page browser behavior", () => {
  test.beforeEach(async ({ page }) => {
    await installAuthenticatedMysticAuthApiRoutes(page);
  });

  test("tabs support profile editing, password validation, appearance controls, and delete cancel", async ({ page }) => {
    await page.goto("/account-settings");

    await page.getByRole("textbox", { name: /^name$/i }).fill("Updated Playwright");
    await page.getByRole("button", { name: /save changes/i }).click();
    await expect(page.getByRole("textbox", { name: /^name$/i })).toHaveValue("Updated Playwright");

    await page.getByRole("tab", { name: /password/i }).click();
    await page.getByPlaceholder(/leave blank to keep your current password/i).fill("weak");
    await page.getByRole("button", { name: /update password/i }).click();
    await expect(page.getByText("Password must be at least 8 characters long")).toBeVisible();

    await page.getByRole("tab", { name: /appearance/i }).click();
    await expect(page.getByRole("button", { name: /reset to default/i })).toBeVisible();
    await page.getByRole("button", { name: /switch to dark mode/i }).click();

    await page.getByRole("tab", { name: /delete account/i }).click();
    await page.getByPlaceholder("Required to confirm this action").fill("anything");
    await page.getByRole("button", { name: /delete my account/i }).click();
    await expect(page.getByRole("alertdialog")).toBeVisible();
    await page.keyboard.press("Escape");
    await expect(page.getByRole("alertdialog")).toBeHidden();
  });
});
