import { expect, test } from "../../../../../frontend/e2e/playwright";
import { installAuthenticatedMysticAuthApiRoutes } from "../support/authenticatedMysticAuthApiRoutes";

type VitalSnapshot = { lcp: number | null; inp: number | null };

const enabled = process.env.RUN_FRONTEND_PERF === "1";
const lcpBudget = Number(process.env.FRONTEND_LCP_BUDGET_MS ?? 0);
const inpBudget = Number(process.env.FRONTEND_INP_BUDGET_MS ?? 0);

test.describe("core web vitals baseline", () => {
  test.skip(!enabled, "Set RUN_FRONTEND_PERF=1 to run the opt-in performance baseline.");

  test.beforeEach(async ({ page }) => {
    await page.addInitScript(() => {
      const state = { lcp: null as number | null, inp: null as number | null };
      (window as Window & { __mysticAuthVitals?: typeof state }).__mysticAuthVitals = state;

      try {
        new PerformanceObserver((list) => {
          const last = list.getEntries().at(-1);
          if (last) state.lcp = last.startTime;
        }).observe({ type: "largest-contentful-paint", buffered: true });
      } catch {
        // Keep navigation working in engines without this observer.
      }

      try {
        new PerformanceObserver((list) => {
          for (const entry of list.getEntries() as PerformanceEventTiming[]) {
            if (entry.duration > (state.inp ?? 0)) state.inp = entry.duration;
          }
        }).observe({ type: "event", buffered: true, durationThreshold: 16 } as PerformanceObserverInit);
      } catch {
        // INP is unavailable in some browser engines.
      }
    });
  });

  for (const [name, path, marker] of [
    ["dashboard", "/dashboard", "Playwright System"],
    ["audit log", "/audit-log", "Audit Log"],
  ] as const) {
    test(`${name} records LCP and an interaction sample`, async ({ page }) => {
      await installAuthenticatedMysticAuthApiRoutes(page);
      await page.goto(path);
      await expect(page.getByRole("heading", { name: marker, exact: true })).toBeVisible();
      // Keyboard input works across desktop and mobile layouts; the first
      // navigation link may be behind the collapsed mobile sidebar.
      await page.keyboard.press("Tab");
      await page.waitForTimeout(250);

      const vitals = await page.evaluate(() => {
        const state = (window as Window & { __mysticAuthVitals?: VitalSnapshot }).__mysticAuthVitals;
        return state ?? { lcp: null, inp: null };
      });
      console.log(`${name} vitals: ${JSON.stringify(vitals)}`);
      expect(vitals.lcp, "LCP observer did not produce a sample").not.toBeNull();
      expect(vitals.inp, "interaction observer did not produce a sample").not.toBeNull();
      if (lcpBudget > 0) expect(vitals.lcp).toBeLessThanOrEqual(lcpBudget);
      if (inpBudget > 0) expect(vitals.inp).toBeLessThanOrEqual(inpBudget);
    });
  }
});
