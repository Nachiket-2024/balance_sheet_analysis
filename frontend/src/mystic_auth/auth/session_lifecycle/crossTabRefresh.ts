import type { AxiosResponse } from "axios";

const WEB_LOCK_NAME = "mystic-auth-refresh-token-rotation";
const LEASE_KEY = "mystic-auth:refresh-lease";
const ROTATION_RESULT_KEY = "mystic-auth:refresh-rotation-result";
const CHANNEL_NAME = "mystic-auth-session";
const LEASE_MS = 15_000;
const HEARTBEAT_MS = 5_000;

type RefreshRequest = () => Promise<AxiosResponse<unknown>>;
type Lease = { owner: string; expiresAt: number };
type RotationResult = { epoch: number; success: boolean };

const tabId = `${Date.now().toString(36)}-${Math.random().toString(36).slice(2)}`;
let channel: BroadcastChannel | null = null;

function getChannel(): BroadcastChannel | null {
  if (typeof BroadcastChannel === "undefined") return null;
  channel ??= new BroadcastChannel(CHANNEL_NAME);
  return channel;
}

function readLease(): Lease | null {
  try {
    const value = window.localStorage.getItem(LEASE_KEY);
    if (!value) return null;
    const parsed = JSON.parse(value) as Partial<Lease>;
    return typeof parsed.owner === "string" && typeof parsed.expiresAt === "number"
      ? { owner: parsed.owner, expiresAt: parsed.expiresAt }
      : null;
  } catch {
    return null;
  }
}

function writeLease(lease: Lease): boolean {
  try {
    window.localStorage.setItem(LEASE_KEY, JSON.stringify(lease));
    return readLease()?.owner === lease.owner;
  } catch {
    return false;
  }
}

function releaseLease(): void {
  try {
    if (readLease()?.owner === tabId) window.localStorage.removeItem(LEASE_KEY);
  } catch {
    // Storage can be unavailable in privacy-restricted contexts. The lease
    // will expire naturally in that case.
  }
  getChannel()?.postMessage({ type: "refresh-finished" });
}

function readRotationResult(): RotationResult | null {
  try {
    const value = window.localStorage.getItem(ROTATION_RESULT_KEY);
    if (!value) return null;
    const parsed = JSON.parse(value) as Partial<RotationResult>;
    return typeof parsed.epoch === "number" && typeof parsed.success === "boolean"
      ? { epoch: parsed.epoch, success: parsed.success }
      : null;
  } catch {
    return null;
  }
}

function publishRotationResult(success: boolean): void {
  try {
    const previous = readRotationResult();
    window.localStorage.setItem(
      ROTATION_RESULT_KEY,
      JSON.stringify({ epoch: (previous?.epoch ?? 0) + 1, success }),
    );
  } catch {
    // If storage is unavailable, the backend remains the final replay guard.
  }
}

function rotationCompletedAfter(before: RotationResult | null): boolean {
  const after = readRotationResult();
  return !!after && (!before || after.epoch !== before.epoch) && after.success;
}

function alreadyRotatedResponse(): AxiosResponse<unknown> {
  return {
    data: { message: "Tokens refreshed in another tab" },
    status: 200,
    statusText: "OK",
    headers: {},
    config: {},
  } as AxiosResponse<unknown>;
}

function waitForAnotherTab(): Promise<void> {
  return new Promise((resolve) => {
    const activeChannel = getChannel();
    const timerRef = { current: 0 };
    const finish = () => {
      window.clearTimeout(timerRef.current);
      activeChannel?.removeEventListener("message", onMessage);
      window.removeEventListener("storage", onStorage);
      resolve();
    };
    const onMessage = (event: MessageEvent<{ type?: string }>) => {
      if (event.data?.type === "refresh-finished") finish();
    };
    const onStorage = (event: StorageEvent) => {
      if (event.key === LEASE_KEY && !readLease()) finish();
    };
    activeChannel?.addEventListener("message", onMessage);
    window.addEventListener("storage", onStorage);
    timerRef.current = window.setTimeout(finish, LEASE_MS);
  });
}

async function refreshWithStorageLease(request: RefreshRequest): Promise<AxiosResponse<unknown>> {
  // This is a fallback for browsers without Web Locks (or restricted storage).
  // The write-then-read verification prevents the normal two-tab race, while
  // the expiry and heartbeat ensure a crashed tab cannot hold the lease forever.
  const rotationBefore = readRotationResult();
  for (;;) {
    const existing = readLease();
    if (existing && existing.owner !== tabId && existing.expiresAt > Date.now()) {
      await waitForAnotherTab();
      if (rotationCompletedAfter(rotationBefore)) return alreadyRotatedResponse();
      continue;
    }

    const lease: Lease = { owner: tabId, expiresAt: Date.now() + LEASE_MS };
    if (!writeLease(lease)) {
      await new Promise((resolve) => window.setTimeout(resolve, 25));
      continue;
    }

    if (rotationCompletedAfter(rotationBefore)) {
      releaseLease();
      return alreadyRotatedResponse();
    }

    const heartbeat = window.setInterval(() => {
      if (readLease()?.owner === tabId) {
        writeLease({ owner: tabId, expiresAt: Date.now() + LEASE_MS });
      }
    }, HEARTBEAT_MS);
    try {
      try {
        const response = await request();
        publishRotationResult(true);
        return response;
      } catch (error) {
        publishRotationResult(false);
        throw error;
      }
    } finally {
      window.clearInterval(heartbeat);
      releaseLease();
    }
  }
}

/** Serialize refresh-token rotation across tabs. Web Locks is the primary
 * mechanism; the lease fallback covers browsers that do not expose it. */
export function runCrossTabRefresh(request: RefreshRequest): Promise<AxiosResponse<unknown>> {
  if (typeof navigator !== "undefined" && "locks" in navigator) {
    const rotationBefore = readRotationResult();
    return navigator.locks.request(WEB_LOCK_NAME, { mode: "exclusive" }, async () => {
      if (rotationCompletedAfter(rotationBefore)) return alreadyRotatedResponse();
      try {
        const response = await request();
        publishRotationResult(true);
        return response;
      } catch (error) {
        publishRotationResult(false);
        throw error;
      }
    });
  }
  return refreshWithStorageLease(request);
}
