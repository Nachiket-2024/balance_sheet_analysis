import { describe, it, expect, afterEach, vi } from "vitest";
import type { AxiosResponse } from "axios";

import { runCrossTabRefresh } from "@/auth/session_lifecycle/crossTabRefresh";

describe("cross-tab refresh coordination", () => {
  const originalLocks = Object.getOwnPropertyDescriptor(Navigator.prototype, "locks");

  afterEach(() => {
    localStorage.removeItem("mystic-auth:refresh-rotation-result");
    if (originalLocks) Object.defineProperty(Navigator.prototype, "locks", originalLocks);
    else Reflect.deleteProperty(navigator, "locks");
  });

  it("uses the browser Web Lock to serialize refresh-token rotation", async () => {
    const request = vi.fn(async () => ({ data: { message: "refreshed" } } as AxiosResponse<unknown>));
    const lockRequest = vi.fn(async (_name: string, _options: { mode: "exclusive" }, callback: () => Promise<unknown>) => callback());
    Object.defineProperty(navigator, "locks", { configurable: true, value: { request: lockRequest } });

    await runCrossTabRefresh(request);

    expect(lockRequest).toHaveBeenCalledWith(
      "mystic-auth-refresh-token-rotation",
      { mode: "exclusive" },
      expect.any(Function),
    );
    expect(request).toHaveBeenCalledTimes(1);
  });

  it("does not rotate again when another tab already completed the refresh", async () => {
    let releaseFirstRequest!: (response: AxiosResponse<unknown>) => void;
    const request = vi.fn(() => new Promise<AxiosResponse<unknown>>((resolve) => {
      releaseFirstRequest = resolve;
    }));
    let locked = false;
    const waiters: Array<() => void> = [];
    const lockRequest = vi.fn(async (_name: string, _options: { mode: "exclusive" }, callback: () => Promise<unknown>) => {
      if (locked) await new Promise<void>((resolve) => waiters.push(resolve));
      locked = true;
      try {
        return await callback();
      } finally {
        locked = false;
        waiters.shift()?.();
      }
    });
    Object.defineProperty(navigator, "locks", { configurable: true, value: { request: lockRequest } });

    const firstRefresh = runCrossTabRefresh(request);
    await vi.waitFor(() => expect(request).toHaveBeenCalledTimes(1));
    const secondRefresh = runCrossTabRefresh(request);
    releaseFirstRequest({ data: { message: "refreshed" } } as AxiosResponse<unknown>);
    await Promise.all([firstRefresh, secondRefresh]);

    expect(request).toHaveBeenCalledTimes(1);
  });
});
