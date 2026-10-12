import type { Page } from "@playwright/test";

import { expect, test } from "../../../../../frontend/e2e/playwright";
import { expectNoHorizontalOverflow } from "../support/browserLayoutAssertions";
import { API_BASE_URL, fulfillJson, installAuthenticatedMysticAuthApiRoutes } from "../support/authenticatedMysticAuthApiRoutes";

// The shared mock returns no sessions (empty state, no table), so the width
// check below needs real rows. Long enough values to catch a tight column.
const SESSIONS = [
  {
    id: 1,
    ip_address: "203.0.113.200",
    city: "Mumbai",
    country: "India",
    user_agent: "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/120.0.0.0",
    created_at: "2026-01-01T09:30:00Z",
    last_used_at: "2026-01-15T21:45:00Z",
    is_current: true,
  },
  {
    id: 2,
    ip_address: "198.51.100.23",
    city: null,
    country: null,
    user_agent: "Mozilla/5.0 (Macintosh; Intel Mac OS X 14_0) Firefox/121.0",
    created_at: "2025-12-24T18:05:00Z",
    last_used_at: "2026-01-14T11:10:00Z",
    is_current: false,
  },
];

// expectNoHorizontalOverflow only checks the page's own scroll width, which
// misses content clipped inside a card. This checks every button in <main>
// actually sits inside the viewport, except buttons inside a horizontally
// scrollable area (like a table), which are reachable by scrolling it.
async function expectMainButtonsInsideViewport(page: Page) {
  const outside = await page.evaluate(() =>
    Array.from(document.querySelectorAll<HTMLElement>("main button"))
      .filter((button) => {
        for (let el = button.parentElement; el && el.tagName !== "MAIN"; el = el.parentElement) {
          const overflowX = window.getComputedStyle(el).overflowX;
          if (overflowX === "auto" || overflowX === "scroll") return false;
        }
        const rect = button.getBoundingClientRect();
        return rect.width > 0 && (rect.left < 0 || rect.right > window.innerWidth + 1);
      })
      .map((button) => button.textContent?.trim() || button.getAttribute("aria-label") || "button"),
  );
  expect(outside).toEqual([]);
}

test.describe("dashboard page browser behavior", () => {
  test.beforeEach(async ({ page }) => {
    await installAuthenticatedMysticAuthApiRoutes(page);
  });

  test("main actions and layout render at desktop and mobile sizes", async ({ page }) => {
    await page.setViewportSize({ width: 1366, height: 900 });
    await page.goto("/dashboard");
    await expect(page.getByRole("heading", { name: "Playwright System" })).toBeVisible();
    await expect(page.getByRole("button", { name: /change password/i })).toBeVisible();
    await expect(page.getByRole("button", { name: /log out everywhere/i })).toBeVisible();
    await expect(page.getByRole("heading", { name: "Management" })).toBeVisible();

    for (const width of [390, 360]) {
      await page.setViewportSize({ width, height: 844 });
      await expect(page.getByRole("heading", { name: "Playwright System" })).toBeVisible();
      await expectNoHorizontalOverflow(page);
      await expectMainButtonsInsideViewport(page);
    }
  });

  test("wide screens cap the content width and keep the management tiles on one row", async ({ page }, testInfo) => {
    // Desktop widths only: the mobile project emulates a phone (Pixel 7), and
    // forcing a 1280px+ viewport onto it isn't a real-world combination.
    test.skip(testInfo.project.name === "chromium-mobile", "desktop-width layout check");
    // Registered after the shared routes, so it takes precedence.
    await page.route(`${API_BASE_URL}/auth/sessions**`, (route) => fulfillJson(route, SESSIONS));
    const identityHeading = page.getByRole("heading", { name: "Playwright System" });
    const managementHeading = page.getByRole("heading", { name: "Management" });
    // Tiles are the buttons inside the Operations shortcuts card's grid.
    const tiles = page.locator("main").getByRole("button").filter({ has: page.locator("p", { hasText: /^(Users|Policies|Permissions|Rate Limits|Security Events)$/ }) });

    for (const [width, height] of [[1280, 800], [1440, 900], [1920, 1080], [2560, 1440]]) {
      await page.setViewportSize({ width, height });
      if (width === 1280) await page.goto("/dashboard");

      // The sessions table fits without scrolling sideways at desktop widths.
      await expect(async () => {
        const tableFits = await page.evaluate(() => {
          const scroller = document.querySelector("#active-sessions table")?.parentElement;
          return !!scroller && scroller.scrollWidth <= scroller.clientWidth + 1;
        });
        expect(tableFits).toBe(true);
      }).toPass();
      await expect(tiles).toHaveCount(5);

      await expect(async () => {
        // Cards stack at every width.
        const identity = await identityHeading.boundingBox();
    const management = await managementHeading.boundingBox();
    expect(management!.y).toBeGreaterThan(identity!.y + 100);

        // All five tiles share one row at every desktop width. Below about
        // 1440px they switch to the compact tile style to fit.
        const tops = await Promise.all((await tiles.all()).map(async (tile) => Math.round((await tile.boundingBox())!.y)));
        expect(new Set(tops).size).toBe(1);

        // Compact labels truncate instead of wrapping onto a second line.
        const labelsWrap = await tiles.evaluateAll((els) =>
          els.some((el) => {
            const label = el.querySelector<HTMLElement>(".tile-label");
            return !!label && label.getBoundingClientRect().height > parseFloat(getComputedStyle(label).lineHeight) * 1.5;
          }),
        );
        expect(labelsWrap).toBe(false);

        // The sessions card never grows past the 90rem content cap.
        const sessions = await page.locator("#active-sessions").boundingBox();
        expect(sessions!.width).toBeLessThanOrEqual(1440 + 1);
      }).toPass();
      await expectNoHorizontalOverflow(page);
    }
  });

  test("the active sessions stat jumps to the sessions card", async ({ page }) => {
    await page.setViewportSize({ width: 390, height: 844 });
    await page.goto("/dashboard");

    await page.getByRole("button", { name: /go to the sessions list/i }).click();

    await expect(page.locator("#active-sessions")).toBeFocused();
    await expect(page.getByRole("heading", { name: "Active Sessions", exact: true })).toBeInViewport({ ratio: 1 });
  });
});
