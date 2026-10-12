import { expect, test } from "../../../../../frontend/e2e/playwright";
import { expectNoHorizontalOverflow } from "../support/browserLayoutAssertions";
import { fulfillUnauthenticatedAuthJson } from "../support/unauthenticatedAuthApiResponses";

test.describe("confirm delete account browser behavior", () => {
  test("confirmation page does not submit without a token", async ({ page }) => {
    let confirmRequests = 0;
    await page.route("**/users/me/confirm-delete", (route) => {
      confirmRequests += 1;
      return route.abort();
    });

    await page.goto("/confirm-delete");
    await expect(page.getByRole("heading", { name: /delete your account/i })).toBeVisible();
    await expect(page.getByRole("button", { name: /^delete my account$/i })).toBeDisabled();
    await expectNoHorizontalOverflow(page);
    expect(confirmRequests).toBe(0);
  });

  test("confirmation page redeems a token through the stubbed endpoint and returns to login", async ({ page }) => {
    await page.route("**/users/me/confirm-delete", async (route) => {
      expect(route.request().postDataJSON()).toEqual({ token: "delete-token" });
      return fulfillUnauthenticatedAuthJson(route, { message: "Account deleted." });
    });

    await page.goto("/confirm-delete#token=delete-token");
    await page.getByRole("button", { name: /^delete my account$/i }).click();
    await expect(page).toHaveURL(/\/login$/);
  });
});
