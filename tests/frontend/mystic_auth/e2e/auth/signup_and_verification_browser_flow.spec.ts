import { expect, test } from "../../../../../frontend/e2e/playwright";
import { expectNoHorizontalOverflow, expectXssNotExecuted } from "../support/browserLayoutAssertions";
import { fulfillUnauthenticatedAuthJson } from "../support/unauthenticatedAuthApiResponses";

test.describe("signup and verification browser behavior", () => {
  test("signup validates passwords locally and submits only to the stubbed signup endpoint", async ({ page }) => {
    let signupRequests = 0;
    await page.route("**/auth/signup", async (route) => {
      signupRequests += 1;
      const payload = route.request().postDataJSON() as { name: string; email: string; password: string };
      expect(payload.name).toBe("<script>window.__xssSignup = true</script>");
      expect(payload.email).toBe("signup-browser@example.com");
      expect(payload.password).toBe("ValidPass123");
      return fulfillUnauthenticatedAuthJson(route, { message: "Check your email to verify your account." });
    });

    await page.goto("/signup");
    await expect(page.getByRole("heading", { name: /create your account/i })).toBeVisible();
    await expectNoHorizontalOverflow(page);

    await page.getByRole("textbox", { name: /^name$/i }).fill("<script>window.__xssSignup = true</script>");
    await page.getByRole("textbox", { name: /^email$/i }).fill("signup-browser@example.com");
    await page.getByPlaceholder("Enter password").fill("short");
    await page.getByPlaceholder("Confirm password").fill("different");
    await page.getByRole("button", { name: /^sign up$/i }).click();
    expect(signupRequests).toBe(0);
    // U3: a failing password rule flags the field and moves focus there
    // instead of repeating the rule as prose in an alert (the checklist
    // below the field already shows it live).
    await expect(page.getByPlaceholder("Enter password")).toBeFocused();
    await expect(page.getByPlaceholder("Enter password")).toHaveAttribute("aria-invalid", "true");

    await page.getByPlaceholder("Enter password").fill("ValidPass123");
    await page.getByPlaceholder("Confirm password").fill("ValidPass123");
    await page.getByRole("button", { name: /^sign up$/i }).click();
    await expect(page.getByText(/check your email/i)).toBeVisible();
    expect(signupRequests).toBe(1);
    await expectXssNotExecuted(page);
  });

  test("verification request and token confirmation use stubbed endpoints", async ({ page }) => {
    let requestCount = 0;
    let verifyCount = 0;
    await page.route("**/auth/verify-account/request", async (route) => {
      requestCount += 1;
      expect(route.request().postDataJSON()).toEqual({ email: "verify-browser@example.com" });
      return fulfillUnauthenticatedAuthJson(route, { message: "Verification link sent." });
    });
    await page.route("**/auth/verify-account", async (route) => {
      verifyCount += 1;
      expect(route.request().postDataJSON()).toEqual({ token: "verify-token" });
      return fulfillUnauthenticatedAuthJson(route, { message: "Account verified." });
    });

    await page.goto("/verify-account?email=verify-browser@example.com");
    await page.getByRole("button", { name: /resend verification email/i }).click();
    await expect(page.getByText(/verification link sent/i)).toBeVisible();
    expect(requestCount).toBe(1);

    await page.goto("/verify-account?token=verify-token&email=verify-browser@example.com");
    await expect(page).toHaveURL(/\/verify-account$/);
    await page.getByRole("button", { name: /^verify email$/i }).click();
    await expect(page).toHaveURL(/\/login$/);
    expect(verifyCount).toBe(1);
  });
});
