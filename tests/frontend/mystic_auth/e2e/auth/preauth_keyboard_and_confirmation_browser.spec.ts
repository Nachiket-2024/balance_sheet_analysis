import { expect, test } from "../../../../../frontend/e2e/playwright";
import { fulfillUnauthenticatedAuthJson } from "../support/unauthenticatedAuthApiResponses";

test.describe("pre-auth keyboard and confirmation behavior", () => {
  test("login keyboard flow reaches reset and legal links without mouse events", async ({ page }) => {
    await page.goto("/login");
    const email = page.getByRole("textbox", { name: /email/i });
    await email.fill("keyboard@example.com");
    await email.press("Tab");
    await expect(page.getByRole("link", { name: /forgot password/i })).toBeFocused();
    await page.getByRole("link", { name: /forgot password/i }).focus();
    await page.keyboard.press("Enter");
    await expect(page).toHaveURL(/\/password-reset-request$/);
  });

  test("reset request Enter submits once and the result button is cooldown-disabled", async ({ page }) => {
    let requests = 0;
    await page.route("**/auth/password-reset/request", async (route) => {
      requests += 1;
      return fulfillUnauthenticatedAuthJson(route, { message: "Reset mail queued." });
    });
    await page.goto("/password-reset-request");
    await page.getByRole("textbox", { name: /^email$/i }).fill("keyboard-reset@example.com");
    await page.keyboard.press("Tab");
    await expect(page.getByRole("button", { name: /send reset link/i })).toBeFocused();
    await page.keyboard.press("Enter");
    await expect(page.getByText(/reset mail queued/i)).toBeVisible();
    await expect(page.getByRole("button", { name: /resend in/i })).toBeDisabled();
    expect(requests).toBe(1);
  });

  test("verification without a token is visibly disabled, while resend uses Space", async ({ page }) => {
    let requests = 0;
    await page.route("**/auth/verify-account/request", async (route) => {
      requests += 1;
      return fulfillUnauthenticatedAuthJson(route, { message: "Verification mail queued." });
    });
    await page.goto("/verify-account");
    await expect(page.getByRole("button", { name: /verify email/i })).toBeDisabled();
    const email = page.getByRole("textbox", { name: /^email$/i });
    await email.fill("verify-keyboard@example.com");
    await page.getByRole("button", { name: /resend verification email/i }).focus();
    await page.keyboard.press("Space");
    await expect(page.getByText(/verification mail queued/i)).toBeVisible();
    expect(requests).toBe(1);
  });

  test("delete confirmation cancel returns home and token confirm redirects to login", async ({ page }) => {
    await page.goto("/confirm-delete");
    await expect(page.getByRole("button", { name: /delete my account/i }).first()).toBeDisabled();
    await page.getByRole("link", { name: /keep my account/i }).focus();
    await page.keyboard.press("Enter");
    await expect(page).toHaveURL(/\/$/);

    let confirmations = 0;
    await page.route("**/users/me/confirm-delete", async (route) => {
      confirmations += 1;
      return fulfillUnauthenticatedAuthJson(route, { message: "Account deleted." });
    });
    await page.goto("/confirm-delete?token=delete-keyboard-token");
    await expect(page).toHaveURL(/\/confirm-delete$/);
    await page.getByRole("button", { name: /delete my account/i }).last().focus();
    await page.keyboard.press("Space");
    await expect(page).toHaveURL(/\/login$/);
    expect(confirmations).toBe(1);
  });

  test("password reset confirmation exposes a local mismatch and submits with Enter", async ({ page }) => {
    let requests = 0;
    await page.route("**/auth/password-reset/confirm", async (route) => {
      requests += 1;
      return fulfillUnauthenticatedAuthJson(route, { message: "Password reset.", sessions_revoked: true });
    });
    await page.goto("/reset-password#token=keyboard-reset-token");
    await page.getByRole("textbox", { name: /^new password$/i }).fill("ValidPass123!");
    const confirmation = page.getByRole("textbox", { name: /^confirm new password$/i });
    await confirmation.fill("Mismatch123!");
    await confirmation.press("Enter");
    await expect(page.getByText(/passwords do not match/i)).toBeVisible();
    expect(requests).toBe(0);

    await confirmation.fill("ValidPass123!");
    await confirmation.press("Enter");
    await expect(page.getByText(/password updated/i)).toBeVisible();
    expect(requests).toBe(1);
  });
});
