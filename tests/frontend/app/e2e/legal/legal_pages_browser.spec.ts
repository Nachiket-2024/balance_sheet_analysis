import { expect, test } from "../../../../../frontend/e2e/playwright";
import { expectNoHorizontalOverflow } from "../../../mystic_auth/e2e/support/browserLayoutAssertions";

test.describe("legal pages browser behavior", () => {
  test("privacy and terms pages render at mobile width", async ({ page }) => {
    await page.setViewportSize({ width: 390, height: 844 });

    await page.goto("/privacy");
    await expect(page.getByRole("heading", { name: /privacy policy/i })).toBeVisible();
    await expectNoHorizontalOverflow(page);

    await page.goto("/terms");
    await expect(page.getByRole("heading", { name: /terms of service/i })).toBeVisible();
    await expectNoHorizontalOverflow(page);
  });
});
