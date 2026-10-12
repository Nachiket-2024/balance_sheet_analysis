// Covers mystic_auth-owned behavior only: the shared ControlCluster
// component's interactive state (rendered via AuthLayout, not the
// app-owned landing page), the login page's own legal-link wiring, and
// the authenticated-root-redirect route guard. Landing page content,
// legal document content, and the 404/404 status pages themselves are
// app-owned (frontend/src/app/{landing_page,legal,status_pages}/) and
// have their own app-neutral coverage under
// tests/frontend/app/e2e/{landing,legal,status_pages}/ - this file must
// never duplicate or hard-code assertions against that app-owned
// content. See docs/mystic_auth/testing/frontend-e2e.md#app-and-public-pages.
import { expect, test } from "../../../../../frontend/e2e/playwright";
import { installAuthenticatedMysticAuthApiRoutes, leastPrivilegeProfile } from "../support/authenticatedMysticAuthApiRoutes";

test.describe("public pages: mystic_auth-owned behavior", () => {
  test("display controls change state and close their menus with Escape", async ({ page }) => {
    // /login, not "/": AuthLayout (and therefore ControlCluster) is
    // mystic_auth-owned regardless of which page renders it, but /login
    // itself is unambiguously mystic_auth-owned too, so this test has no
    // dependency on the app-owned landing page at all.
    await page.goto("/login");

    const theme = page.getByRole("button", { name: /switch to dark mode|switch to light mode/i });
    const initialThemeLabel = await theme.getAttribute("aria-label");
    await theme.focus();
    await page.keyboard.press("Space");
    await expect(theme).not.toHaveAttribute("aria-label", initialThemeLabel ?? "");

    const fontSize = page.getByRole("combobox", { name: /font size/i });
    await fontSize.focus();
    await page.keyboard.press("Enter");
    await expect(page.getByRole("option").first()).toBeVisible();
    await page.keyboard.press("ArrowDown");
    await page.keyboard.press("Enter");
    await expect(page.locator("html")).toHaveCSS("font-size", /.+/);

    const language = page.getByRole("combobox", { name: /language/i });
    await language.focus();
    await page.keyboard.press("Enter");
    await expect(page.getByRole("option").first()).toBeVisible();
    await page.keyboard.press("Escape");
    await expect(page.getByRole("option").first()).toBeHidden();
    await expect(language).toBeFocused();
  });

  test("login page's legal links navigate away and back, preserving the triggering route", async ({ page }) => {
    // Asserts only the login page's own link wiring and browser-history
    // behavior (both mystic_auth-owned) - never the legal page's
    // destination content, which is app-owned and covered by
    // tests/frontend/app/e2e/legal/legal_pages_browser.spec.ts.
    await page.goto("/login");
    await page.getByRole("link", { name: /terms of service/i }).click();
    await expect(page).toHaveURL(/\/terms$/);
    const back = page.getByRole("button", { name: /back/i }).first();
    await back.focus();
    await page.keyboard.press("Enter");
    await expect(page).toHaveURL(/\/login$/);
  });

  test("an authenticated user visiting the public root is redirected to the dashboard", async ({ page }) => {
    // The public-root-redirects-signed-in-users rule is mystic_auth's own
    // routing behavior. Going straight to "/" while authenticated isolates
    // that rule from the app-owned NotAuthorizedPage/LandingPage markup
    // entirely, unlike the previous version of this test, which clicked
    // through the 403 page's "Go Home" button and hard-coded its heading.
    await installAuthenticatedMysticAuthApiRoutes(page, leastPrivilegeProfile);
    await page.goto("/");
    await expect(page).toHaveURL(/\/dashboard$/);
  });
});
