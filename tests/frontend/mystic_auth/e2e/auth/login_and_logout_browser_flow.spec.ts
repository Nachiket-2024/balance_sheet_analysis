import { expect, test } from "../../../../../frontend/e2e/playwright";
import { API_BASE_URL } from "../support/authenticatedMysticAuthApiRoutes";
import { deleteBrowserSystemUser, SEEDED_PASSWORD, seedBrowserSystemUser, seededSystemEmail } from "../support/disposableSystemUser";

test.describe("auth and routing in a real browser", () => {
  test("login page renders and blocks empty submissions locally", async ({ page }) => {
    let loginRequests = 0;
    await page.route("**/auth/login", (route) => {
      loginRequests += 1;
      return route.fulfill({ status: 400, json: { detail: "Invalid credentials" } });
    });

    await page.goto("/login");
    await expect(page.getByText(/welcome back/i)).toBeVisible();
    await expect(page.getByRole("textbox", { name: /email/i })).toBeVisible();
    await expect(page.getByRole("textbox", { name: /^password$/i })).toBeVisible();

    await page.getByRole("button", { name: /^log in$/i }).click();
    expect(loginRequests).toBe(0);
    await expect(page.getByRole("textbox", { name: /email/i })).toBeFocused();
  });

  test("shows a retry action after a network failure and completes the login on retry", async ({ page }) => {
    let loginAttempts = 0;

    // The dashboard mounts several background queries immediately after the
    // redirect. Abort those unrelated requests so a backend 401 cannot make
    // the axios session interceptor log this test back out, and malformed
    // placeholder JSON cannot trip the app error boundary.
    await page.route(`${API_BASE_URL}/**`, (route) => {
      if (new URL(route.request().url()).pathname === "/auth/login") return route.fallback();
      return route.abort("blockedbyclient");
    });
    await page.route("**/auth/login", async (route) => {
      loginAttempts += 1;
      if (loginAttempts === 1) {
        await route.abort("failed");
        return;
      }
      await route.fulfill({ status: 200, json: { message: "Login successful" } });
    });

    // Keep the initial session probe unauthenticated, then return the profile
    // only after the mocked login succeeds. No account or email flow is used.
    await page.route("**/auth/me*", async (route) => {
      if (loginAttempts < 2) {
        await route.fulfill({ status: 401, json: { error: "Not authenticated" } });
        return;
      }
      await route.fulfill({
        status: 200,
        json: { name: "Retry User", email: "retry-login@example.test", role: "user", permissions: [] },
      });
    });

    await page.goto("/login");
    await page.getByRole("textbox", { name: /email/i }).fill("retry-login@example.test");
    await page.getByRole("textbox", { name: /^password$/i }).fill("StrongPass123!");
    await page.getByRole("button", { name: /^log in$/i }).click();

    await expect(page.getByRole("alert")).toContainText(/couldn't connect|could not connect/i);
    await expect(page.getByRole("button", { name: /try again/i })).toBeVisible();

    await page.getByRole("button", { name: /try again/i }).click();
    await expect(page).toHaveURL(/\/dashboard$/);
    await expect(page.getByRole("heading", { name: "Retry User" })).toBeVisible();
    expect(loginAttempts).toBe(2);
  });

  test("protected routes redirect logged-out users to login", async ({ page }) => {
    await page.goto("/users");
    await expect(page).toHaveURL(/\/login$/);
    await expect(page.getByText(/welcome back/i)).toBeVisible();
  });

  test("logs in with the disposable seeded system user", async ({ page }, testInfo) => {
    const email = seededSystemEmail(testInfo.project.name);
    seedBrowserSystemUser(email);
    await page.goto("/login");
    await page.getByRole("textbox", { name: /email/i }).fill(email);
    await page.getByRole("textbox", { name: /^password$/i }).fill(SEEDED_PASSWORD);
    await page.getByRole("button", { name: /^log in$/i }).click();

    await expect(page).toHaveURL(/\/dashboard$/);
    await expect(page.getByRole("heading", { name: "Playwright System" })).toBeVisible();
  });

  test("logout returns the browser to the login page", async ({ page }, testInfo) => {
    const email = seededSystemEmail(testInfo.project.name);
    seedBrowserSystemUser(email);
    await page.goto("/login");
    await page.getByRole("textbox", { name: /email/i }).fill(email);
    await page.getByRole("textbox", { name: /^password$/i }).fill(SEEDED_PASSWORD);
    await page.getByRole("button", { name: /^log in$/i }).click();
    await expect(page).toHaveURL(/\/dashboard$/);

    await page.getByRole("button", { name: /^logout$/i }).click();
    await expect(page).toHaveURL(/\/login$/);
  });
});

test.afterEach(({ page }, testInfo) => {
  void page;
  deleteBrowserSystemUser(seededSystemEmail(testInfo.project.name));
});
