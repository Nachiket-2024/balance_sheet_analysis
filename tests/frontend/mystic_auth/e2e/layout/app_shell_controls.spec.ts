import { expect, test } from "../../../../../frontend/e2e/playwright";
import { expectNoHorizontalOverflow } from "../support/browserLayoutAssertions";
import { installAuthenticatedMysticAuthApiRoutes } from "../support/authenticatedMysticAuthApiRoutes";

test.describe("app shell browser controls", () => {
  test.beforeEach(async ({ page }) => {
    await installAuthenticatedMysticAuthApiRoutes(page);
  });

  test("sidebar, navbar, command palette, theme, language, and font controls work", async ({ page }) => {
    await page.setViewportSize({ width: 1366, height: 900 });
    await page.goto("/dashboard");

    await expect(page.getByRole("navigation", { name: /main navigation/i })).toBeVisible();
    await expect(page.getByRole("button", { name: /open search/i })).toBeVisible();
    await page.keyboard.press(process.platform === "darwin" ? "Meta+K" : "Control+K");
    const palette = page.getByRole("dialog");
    await expect(palette).toBeVisible();
    await palette.getByRole("textbox").fill("settings");
    await palette.getByRole("button", { name: /account settings/i }).click();
    await expect(page).toHaveURL(/\/account-settings/);

    await page.getByRole("button", { name: /switch to dark mode/i }).click();
    await expect(page.getByRole("button", { name: /switch to light mode/i })).toBeVisible();
    await expect(page.locator("html")).toHaveClass(/dark/);
    await page.getByRole("button", { name: /switch to light mode/i }).click();
    await expect(page.locator("html")).not.toHaveClass(/dark/);
  });

  // Every language mode actually changes rendered text, not just the
  // dropdown showing an option. The three pure modes (hi/mr/gu) translate
  // both chrome (sidebar/navbar) and page content; the three bilingual
  // modes (en+hi/en+mr/en+gu) deliberately keep chrome in English and only
  // translate page content (see languageStore.ts's resolveLanguages) - the
  // sidebar reading "Users" while the dashboard heading reads "डैशबोर्ड" at
  // the same time is correct, not a bug, so this checks chrome text for
  // pure modes and page-content text for bilingual ones.
  test("every language mode changes rendered chrome or content text correctly", async ({ page }) => {
    await page.setViewportSize({ width: 1366, height: 900 });
    await page.goto("/dashboard");
    // Not getByRole(..., { name: /main navigation/i }): the sidebar's own
    // aria-label is itself translated in pure modes, so a name-based
    // locator would break on the very thing this test is switching. There
    // is exactly one <nav> in AppLayout, so the bare tag is a stable
    // handle across every language.
    const sidebar = page.locator("nav");
    // Dashboard's own <h1>, from DashboardPage.tsx's t("pageTitle") -
    // translates with pageLanguage in every mode, pure or bilingual.
    const pageHeading = page.getByRole("heading", { level: 1 });

    const pureModes: { option: string; navExpect: RegExp; headingExpect: RegExp }[] = [
      { option: "हिंदी (Hindi)", navExpect: /उपयोगकर्ता/, headingExpect: /डैशबोर्ड/ },
      { option: "मराठी (Marathi)", navExpect: /वापरकर्ते/, headingExpect: /डॅशबोर्ड/ },
      { option: "ગુજરાતી (Gujarati)", navExpect: /વપરાશકર્તાઓ/, headingExpect: /ડેશબોર્ડ/ },
    ];
    const bilingualModes: { option: string; expect: RegExp }[] = [
      { option: "English + हिंदी", expect: /डैशबोर्ड/ },
      { option: "English + मराठी", expect: /डॅशबोर्ड/ },
      { option: "English + ગુજરાતી", expect: /ડેશબોર્ડ/ },
    ];

    // Not getByRole(..., { name: /language/i }): this control's own
    // aria-label is drawn from chromeLanguage, which pure modes translate
    // along with everything else, so an English-name locator stops
    // matching after the first non-English selection. The trigger
    // button's icon (lucide's "languages" glyph) is stable across every
    // mode instead.
    const languageTrigger = page.locator("button:has(svg.lucide-languages)");

    for (const { option, navExpect, headingExpect } of pureModes) {
      await languageTrigger.click();
      await page.getByRole("option", { name: option, exact: true }).click();
      await expect(sidebar).toContainText(navExpect);
      await expect(pageHeading).toContainText(headingExpect);
    }
    for (const { option, expect: expectPresent } of bilingualModes) {
      await languageTrigger.click();
      await page.getByRole("option", { name: option, exact: true }).click();
      await expect(sidebar).toContainText("Users");
      await expect(pageHeading).toContainText(expectPresent);
    }
    // Back to plain English: chrome and content both revert.
    await languageTrigger.click();
    await page.getByRole("option", { name: "English", exact: true }).click();
    await expect(sidebar).toContainText("Users");
    await expect(pageHeading).toContainText("Dashboard");
  });

  // Selecting a font size actually resizes the document, not just changes
  // which dropdown option is checked.
  test("every font size option actually resizes the document", async ({ page }) => {
    await page.setViewportSize({ width: 1366, height: 900 });
    await page.goto("/dashboard");

    const sizeFor = (label: string) => {
      return page
        .getByRole("combobox", { name: /font size/i })
        .click()
        .then(() => page.getByRole("option", { name: label, exact: true }).click())
        .then(() => page.evaluate(() => document.documentElement.style.fontSize));
    };

    const small = await sizeFor("Small");
    const medium = await sizeFor("Medium");
    const large = await sizeFor("Large");

    expect(new Set([small, medium, large]).size).toBe(3);
    // Small < Medium < Large as actual percentages, not just three distinct
    // arbitrary strings.
    const toPercent = (v: string) => parseFloat(v);
    expect(toPercent(small)).toBeLessThan(toPercent(medium));
    expect(toPercent(medium)).toBeLessThan(toPercent(large));
  });

  test("responsive menu opens without horizontal overflow or obvious overlap", async ({ page }) => {
    await page.setViewportSize({ width: 390, height: 844 });
    await page.goto("/dashboard");

    await page.getByRole("button", { name: /toggle navigation menu/i }).click();
    await expect(page.getByRole("link", { name: /users/i })).toBeVisible();
    await expectNoHorizontalOverflow(page);
    await page.getByRole("link", { name: /users/i }).click();
    await expect(page).toHaveURL(/\/users$/);
  });
});
