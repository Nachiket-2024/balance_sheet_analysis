import { expect, test } from "../../../../../frontend/e2e/playwright";

test("browser security headers are present and framing is blocked", async ({ page }) => {
  const frameViolations: string[] = [];
  page.on("console", (message) => {
    if (/frame-ancestors|Refused to frame/i.test(message.text())) {
      frameViolations.push(message.text());
    }
  });

  const response = await page.goto("/login");
  expect(response).not.toBeNull();
  const headers = await response!.allHeaders();
  expect(headers["content-security-policy"]).toContain("frame-ancestors 'none'");
  expect(headers["permissions-policy"]).toBeTruthy();
  expect(headers["referrer-policy"]).toBe("no-referrer");
  expect(headers["x-content-type-options"]).toBe("nosniff");
  expect(headers["x-frame-options"]).toBe("DENY");

  await page.evaluate(() => {
    const frame = document.createElement("iframe");
    frame.src = `${window.location.origin}/login`;
    document.body.append(frame);
  });
  await expect.poll(() => frameViolations.length).toBeGreaterThan(0);
  expect(frameViolations.join("\n")).toContain("frame-ancestors");
});
