import { expect, test } from "../../../../../frontend/e2e/playwright";
import { installAuthenticatedMysticAuthApiRoutes } from "../support/authenticatedMysticAuthApiRoutes";
import { expectNoAccessibilityViolations } from "../support/axeCheck";

test.describe("rate limits page browser behavior", () => {
    test.beforeEach(async ({ page }) => {
        await installAuthenticatedMysticAuthApiRoutes(page);
    });

    test("summary cards are keyboard-accessible filter shortcuts", async ({ page }) => {
        await page.goto("/rate-limits");

        const total = page.getByRole("button", { name: "Active counters" });
        const atLimit = page.getByRole("button", { name: "At limit" });
        await expect(total).toBeVisible();
        await expect(atLimit).toBeVisible();
        const lockouts = page.getByRole("button", { name: "Login lockouts" });
        await expect(lockouts).toBeVisible();

        await atLimit.focus();
        await page.keyboard.press("Enter");
        await expect(atLimit).toHaveAttribute("aria-pressed", "true");
        await expect(page).toHaveURL(/rate-limits/);

        await lockouts.focus();
        await page.keyboard.press("Enter");
        await expect(lockouts).toHaveAttribute("aria-pressed", "true");
        await expect(atLimit).toHaveAttribute("aria-pressed", "false");

    });

    test("keeps endpoint dropdown and scope quick filters usable at narrow width", async ({ page }) => {
        await page.setViewportSize({ width: 1280, height: 800 });
        await page.goto("/rate-limits");

        const endpointFilter = page.getByRole("button", { name: "Filter by endpoint" });
        await expect(endpointFilter).toBeVisible();
        await endpointFilter.click();
        await expect(page.getByRole("textbox", { name: "Search endpoints..." })).toBeVisible();
        await page.keyboard.press("Escape");
        await page.getByRole("radio", { name: /IP/ }).click();
        await expect(page.getByRole("radio", { name: /IP/ })).toHaveAttribute("aria-checked", "true");
        await expect(page.getByRole("radio", { name: /Login lockout/i })).toHaveCount(0);
        await expectNoAccessibilityViolations(page);
    });

    test("opens the reset confirmation, cancels safely, and confirms one reset", async ({ page }) => {
        let resetCount = 0;
        await page.route("**/rate-limits/**", async (route) => {
            if (route.request().method() === "DELETE") resetCount += 1;
            await route.fallback();
        });
        await page.goto("/rate-limits");

        const reset = page.getByRole("button", { name: "Reset", exact: true }).first();
        await reset.click();
        const dialog = page.getByRole("alertdialog");
        await expect(dialog).toBeVisible();
        await page.keyboard.press("Escape");
        await expect(dialog).toBeHidden();
        await expect(reset).toBeFocused();
        expect(resetCount).toBe(0);

        await reset.click();
        await dialog.getByRole("button", { name: /^reset$/i }).click();
        await expect(page.getByText(/rate limit reset/i)).toBeVisible();
        expect(resetCount).toBe(1);
    });
});
