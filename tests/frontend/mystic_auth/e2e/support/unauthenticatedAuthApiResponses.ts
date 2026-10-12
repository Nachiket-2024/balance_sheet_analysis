import type { Route } from "@playwright/test";

export function fulfillUnauthenticatedAuthJson(route: Route, json: unknown, status = 200) {
  const browserOrigin = new URL(
    process.env.PLAYWRIGHT_BASE_URL ?? "http://localhost:5173",
  ).origin;
  return route.fulfill({
    status,
    json,
    headers: {
      "access-control-allow-origin": browserOrigin,
      "access-control-allow-credentials": "true",
    },
  });
}
