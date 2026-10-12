import { expect, test } from "../../../../../frontend/e2e/playwright";

test.describe("protected mystic auth route browser behavior", () => {
  test("protected routes send unauthenticated visitors to login", async ({ page }) => {
    await page.goto("/dashboard");

    await expect(page).toHaveURL(/\/login/);
    await expect(page.getByText(/welcome back/i)).toBeVisible();
  });
});
