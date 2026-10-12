import type { Page } from "@playwright/test";
import { expect } from "../../../../../frontend/e2e/playwright";

export async function expectNoHorizontalOverflow(page: Page) {
  const hasOverflow = await page.evaluate(() => document.documentElement.scrollWidth > window.innerWidth);
  expect(hasOverflow).toBe(false);
}

export async function expectNoVisibleOverlap(page: Page) {
  const overlaps = await page.evaluate(() => {
    const selectors = "button,a,input,select,[role='tab'],[role='dialog'],[role='alertdialog']";
    const elements = Array.from(document.querySelectorAll<HTMLElement>(selectors))
      .filter((element) => {
        const rect = element.getBoundingClientRect();
        const style = window.getComputedStyle(element);
        return rect.width > 0 && rect.height > 0 && style.visibility !== "hidden" && style.display !== "none";
      })
      .map((element) => ({ name: element.textContent?.trim() || element.getAttribute("aria-label") || element.tagName, rect: element.getBoundingClientRect() }));

    const findings: string[] = [];
    for (let i = 0; i < elements.length; i += 1) {
      for (let j = i + 1; j < elements.length; j += 1) {
        const a = elements[i].rect;
        const b = elements[j].rect;
        const x = Math.max(0, Math.min(a.right, b.right) - Math.max(a.left, b.left));
        const y = Math.max(0, Math.min(a.bottom, b.bottom) - Math.max(a.top, b.top));
        if (x * y > 24 && !(a.left === b.left && a.top === b.top && a.width === b.width && a.height === b.height)) {
          findings.push(`${elements[i].name} overlaps ${elements[j].name}`);
        }
      }
    }
    return findings.slice(0, 5);
  });
  expect(overlaps).toEqual([]);
}

export async function expectXssNotExecuted(page: Page) {
  await expect.poll(() => page.evaluate(() => Boolean((window as Window & { __xssUser?: boolean }).__xssUser))).toBe(false);
}
