import { expect, test } from "../../../../../frontend/e2e/playwright";
import { expectNoHorizontalOverflow } from "../../../mystic_auth/e2e/support/browserLayoutAssertions";

test.describe("app landing page browser behavior", () => {
  test("landing page renders and keeps auth actions reachable", async ({ page }) => {
    await page.goto("/");

    const brandHome = page.locator('header a[aria-label]').first();
    const brandHomeLabel = await brandHome.getAttribute("aria-label");
    const title = await page.title();

    expect(title).not.toBe("");
    expect(brandHomeLabel).toContain(title);
    await expect(page.getByRole("link", { name: /log in/i }).first()).toBeVisible();
    await expect(page.getByRole("link", { name: /sign up/i }).first()).toBeVisible();
    await expect(page.getByRole("main")).toBeVisible();
    await expect(page.getByRole("heading", { name: /see the balance sheet clearly/i })).toBeVisible();
    await expect(page.getByRole("heading").first()).toBeVisible();
    await expect(page).toHaveTitle(/Balance Sheet Analysis/);
    await expect(page.getByRole("heading", { name: /everything needed for a confident review/i })).toBeVisible();
    await expect(page.getByRole("heading", { name: /import company data/i })).toBeVisible();
  });

  test("supports keyboard skip navigation and remains usable at 125% and 150% zoom", async ({ page }) => {
    await page.goto("/");

    const skipLink = page.getByRole("link", { name: /skip to main content/i });
    await skipLink.focus();
    await expect(skipLink).toBeFocused();
    await page.keyboard.press("Enter");
    await expect(page.getByRole("main")).toBeFocused();

    for (const zoom of ["1.25", "1.5"]) {
      await page.evaluate((value) => { document.documentElement.style.zoom = value; }, zoom);
      await expectNoHorizontalOverflow(page);
      await expect(page.getByRole("main")).toBeVisible();
    }
  });
});
