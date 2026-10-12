import { expect, test } from "../../../../../frontend/e2e/playwright";
import { fulfillJson, installAuthenticatedMysticAuthApiRoutes, policies, policiesReadOnlyProfile } from "../support/authenticatedMysticAuthApiRoutes";

test.describe("policies page browser behavior", () => {
  test.beforeEach(async ({ page }) => {
    await installAuthenticatedMysticAuthApiRoutes(page);
  });

  test("filters and create, edit, delete dialog cancel behavior work", async ({ page }) => {
    await page.goto("/policies");
    await expect(page.getByText("self_service")).toBeVisible();
    await page.getByPlaceholder(/search by name or description/i).fill("policy_admin");
    await page.locator('select[aria-label="Filter by resource type"]').selectOption("policies");
    await page.locator('select[aria-label="Filter by status"]').selectOption("true");

    await page.getByRole("button", { name: /create policy/i }).click();
    await expect(page.getByRole("dialog")).toBeVisible();
    await page.getByRole("button", { name: /close dialog/i }).click();

    const selfServiceCard = page.getByText("self_service").locator("xpath=ancestor::div[.//button[@aria-label='Edit']][1]");
    await expect(selfServiceCard.getByRole("button", { name: /^edit$/i })).toBeDisabled();
    await expect(selfServiceCard.getByRole("button", { name: /^delete$/i })).toHaveCount(0);
  });

  test("keeps the policy page usable at 125% and 150% zoom", async ({ page }) => {
    await page.goto("/policies");
    await expect(page.getByText("policy_admin")).toBeVisible();

    for (const zoom of [1.25, 1.5]) {
      await page.evaluate((value) => {
        document.documentElement.style.zoom = String(value);
      }, zoom);

      const overflow = await page.evaluate(() =>
        document.documentElement.scrollWidth > document.documentElement.clientWidth + 1
      );
      expect(overflow, `unexpected horizontal overflow at ${zoom * 100}% zoom`).toBe(false);
    }

    await page.evaluate(() => {
      document.documentElement.style.zoom = "";
    });
  });

  test("keeps Details and Edit in one dialog and saves Actions immediately with Undo", async ({ page }) => {
    await page.goto("/policies");
    const policyAdminCard = page.getByText("policy_admin", { exact: true }).locator("xpath=ancestor::div[.//button[@aria-label='View']][1]");
    await policyAdminCard.getByRole("button", { name: /^view$/i }).click();

    const dialog = page.getByRole("dialog");
    const detailsTab = dialog.getByRole("tab", { name: /details/i });
    const editTab = dialog.getByRole("tab", { name: /edit/i });
    await expect(detailsTab).toHaveAttribute("aria-selected", "true");
    await expect(dialog.getByText("Manage policies safely").first()).toBeVisible();

    await page.keyboard.press("ArrowRight");
    await expect(editTab).toHaveAttribute("aria-selected", "true");
    await expect(dialog.getByRole("textbox", { name: /^name$/i })).toHaveValue("policy_admin");

    const basicsTab = dialog.getByRole("tab", { name: /Basics/ });
    const actionsTab = dialog.getByRole("tab", { name: /^Actions/ });
    await basicsTab.focus();
    await page.keyboard.press("ArrowRight");
    await expect(actionsTab).toHaveAttribute("aria-selected", "true");
    await expect(dialog.getByRole("button", { name: /save changes/i })).toHaveCount(0);
    await expect(dialog.getByRole("button", { name: /^close$/i })).toBeVisible();

    const updateRequest = page.waitForRequest((request) =>
      request.method() === "PUT" && request.url().endsWith("/authorization/policies/policy_admin"),
    );
    await dialog.getByRole("switch", { name: "Read policies" }).click();
    const request = await updateRequest;
    expect(request.postDataJSON()).toEqual({ actions: ["policies:create", "policies:update"] });

    await expect(page.getByText(/Removed Read policies from "policy_admin"\./)).toBeVisible();
    await page.getByRole("button", { name: "Undo" }).click();
    await expect(page.getByText(/Granted Read policies in "policy_admin"\./)).toBeVisible();
    await expect(dialog.getByRole("switch", { name: "Read policies" })).toBeChecked();
  });

  test("flips the active switch before a slow update response arrives", async ({ page }) => {
    let releaseUpdate!: () => void;
    const updateStarted = new Promise<void>((resolve) => {
      page.route("**/authorization/policies/policy_admin", async (route) => {
        if (route.request().method() !== "PUT") return route.fallback();
        resolve();
        await new Promise<void>((release) => {
          releaseUpdate = release;
        });
        await fulfillJson(route, { ...policies[1], is_active: false });
      });
    });

    await page.goto("/policies");
    const card = page.getByText("policy_admin", { exact: true }).locator("xpath=ancestor::div[.//button[@aria-label='View']][1]");
    const activeSwitch = card.getByRole("switch", { name: "Deactivate" });
    await activeSwitch.click();
    await updateStarted;

    // The delayed request is still open, but the user gets immediate visual
    // feedback and the control is locked against duplicate mutations.
    await expect(card.getByRole("switch", { name: "Activate" })).not.toBeChecked();
    await expect(card.getByRole("switch", { name: "Activate" })).toBeDisabled();

    releaseUpdate();
    await expect(page.getByText(/deactivated/i).last()).toBeVisible();
  });

  test("hides edit-only policy controls from a read-only policy caller", async ({ page }) => {
    await installAuthenticatedMysticAuthApiRoutes(page, policiesReadOnlyProfile);
    await page.goto("/policies");
    const card = page.getByText("policy_admin", { exact: true }).locator("xpath=ancestor::div[.//button[@aria-label='View']][1]");
    await expect(card.getByRole("button", { name: "View" })).toBeVisible();
    await expect(card.getByRole("button", { name: "Edit" })).toHaveCount(0);
    await expect(card.getByRole("switch")).toHaveCount(0);
    await card.getByRole("button", { name: "View" }).click();
    const dialog = page.getByRole("dialog");
    await expect(dialog.getByRole("tab", { name: /details/i })).toBeVisible();
    await expect(dialog.getByRole("tab", { name: /edit/i })).toHaveCount(0);
  });
});
