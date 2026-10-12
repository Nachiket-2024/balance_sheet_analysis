// Use the "/vitest" entry point, not the bare package: it types jest-dom's
// matchers (like `.not`) against Vitest's `expect` instead of Jest's.
import * as matchers from "@testing-library/jest-dom/matchers";
import { expect } from "vitest";
expect.extend(matchers);

// Vitest 5's Assertion type is intentionally minimal in this dependency
// layout, while the runtime still exposes Chai's `.not` chain. Keep the
// matcher typing in sync for tests compiled from the sibling tests/ tree.
declare module "vitest" {
    interface Assertion<R extends void | Promise<void> = void, T = unknown> {
        readonly not: Assertion<R, T>;
        [matcher: string]: (...args: unknown[]) => unknown;
    }
}

import { beforeEach } from "vitest";
import { resetAllSessionUiStores } from "../store/createSessionUiStore";

// Page UI stores (accountSettingsUiStore, usersUiStore, etc.) are in-memory module
// singletons by design (see createSessionUiStore.ts), so state set by one test would
// otherwise leak into the next test in the same file. Reset before every test rather
// than relying on each test file to remember to.
beforeEach(() => {
    resetAllSessionUiStores();
});

// Loads real English translations before any test renders a component.
// Without this, useTranslation() has nothing loaded and renders raw keys
// (e.g. "passwordRules.minLength") instead of the text tests assert against.
import "../translations/translations";

// jsdom has no EventSource. useSessionEventsStream mounts app-wide, so any
// test that renders the authenticated app tree needs this stand-in just to
// avoid a ReferenceError; tests checking its actual behavior mock it themselves.
class MockEventSource {
    onmessage: ((event: MessageEvent) => void) | null = null;
    onerror: ((event: Event) => void) | null = null;
    close(): void {}
}

// @ts-expect-error - a minimal stand-in for tests, not a full EventSource implementation
globalThis.EventSource = MockEventSource;

// jsdom also has no ResizeObserver. Radix's popover components (Select,
// Combobox; see LanguageToggle.tsx) use it via floating-ui to track their
// trigger's position while open, so opening one throws without this stand-in.
class MockResizeObserver {
    observe(): void {}
    unobserve(): void {}
    disconnect(): void {}
}

globalThis.ResizeObserver = MockResizeObserver;

// jsdom also has no Element.scrollTo. Radix's Select (LanguageToggle.tsx)
// calls it on selection to reset scroll position for next open.
if (!Element.prototype.scrollTo) {
    Element.prototype.scrollTo = () => {};
}

// jsdom has no pointer capture APIs or Element.scrollIntoView. Radix's
// Select (ui/filters/StyledSelect.tsx) calls hasPointerCapture/releasePointerCapture
// on pointer events while open, and its Viewport calls scrollIntoView to
// keep the highlighted item visible - both throw "not a function" in jsdom
// without these stand-ins.
if (!Element.prototype.hasPointerCapture) {
    Element.prototype.hasPointerCapture = () => false;
}
if (!Element.prototype.setPointerCapture) {
    Element.prototype.setPointerCapture = () => {};
}
if (!Element.prototype.releasePointerCapture) {
    Element.prototype.releasePointerCapture = () => {};
}
if (!Element.prototype.scrollIntoView) {
    Element.prototype.scrollIntoView = () => {};
}
