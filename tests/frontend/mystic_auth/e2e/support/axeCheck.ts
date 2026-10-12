import type { Page } from "@playwright/test";
import { AxeBuilder } from "../../../../../frontend/e2e/axe";
import { expect } from "../../../../../frontend/e2e/playwright";

// wcag2a/wcag2aa/wcag21a/wcag21aa: the standard "serious accessibility bug"
// tag set axe ships with. Excludes wcag***aaa (a stricter level most sites,
// including this one, don't target) and best-practice-only rules (opinions,
// not violations) so a failure here always means a real WCAG 2.1 AA issue.
const WCAG_AA_TAGS = ["wcag2a", "wcag2aa", "wcag21a", "wcag21aa"];

export async function expectNoAccessibilityViolations(page: Page, options: { exclude?: string[] } = {}) {
  let builder = new AxeBuilder({ page }).withTags(WCAG_AA_TAGS);
  for (const selector of options.exclude ?? []) {
    builder = builder.exclude(selector);
  }
  const results = await builder.analyze();

  if (results.violations.length > 0) {
    const summary = results.violations
      .map((v) => `${v.id} (${v.impact}): ${v.help} - ${v.nodes.length} element(s)\n  ${v.nodes.map((n) => n.target.join(" ")).join("\n  ")}`)
      .join("\n\n");
    expect(results.violations, `Accessibility violations found:\n\n${summary}`).toEqual([]);
  }
}
