import { expect, test } from "../../../../../frontend/e2e/playwright";
import { expectNoHorizontalOverflow } from "../support/browserLayoutAssertions";

test.describe("mystic auth pages responsive browser behavior", () => {
  test("auth pages render without horizontal overflow", async ({ page }) => {
    test.setTimeout(60_000);
    for (const path of ["/login", "/signup", "/password-reset-request", "/reset-password", "/verify-account", "/confirm-delete"]) {
      await page.goto(path);
      await expect(page.locator("#root")).toBeVisible();
      await expectNoHorizontalOverflow(page);
    }
  });

  test("auth pages remain usable at 125% and 150% zoom", async ({ page }) => {
    for (const path of ["/login"]) {
      await page.goto(path);
      for (const zoom of ["1.25", "1.5"]) {
        await page.evaluate((value) => { document.documentElement.style.zoom = value; }, zoom);
        await expectNoHorizontalOverflow(page);
        await expect(page.locator("#root")).toBeVisible();
      }
      await page.evaluate(() => { document.documentElement.style.zoom = ""; });
    }
  });
});
