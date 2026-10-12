import { expect, test } from "../../../../../frontend/e2e/playwright";
import { expectNoHorizontalOverflow } from "../../../mystic_auth/e2e/support/browserLayoutAssertions";

test.describe("status pages browser behavior", () => {
  test("not-authorized and not-found pages render at mobile width", async ({ page }) => {
    await page.setViewportSize({ width: 390, height: 844 });

    await page.goto("/not-authorized");
    await expect(page.locator("#root")).toBeVisible();
    await expectNoHorizontalOverflow(page);

    await page.goto("/missing-page");
    await expect(page.getByRole("heading", { name: "404" })).toBeVisible();
    await expect(page.getByRole("heading", { name: /page not found/i })).toBeVisible();
    await expectNoHorizontalOverflow(page);
  });
});
