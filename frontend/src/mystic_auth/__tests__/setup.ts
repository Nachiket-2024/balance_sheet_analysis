// The "/vitest" entry point (rather than the bare package) augments
// Vitest's own `expect`/Assertion types with jest-dom's matchers.
// The generic entry point targets Jest's types instead, which left
// `.not` and other chained matchers untyped under Vitest.
import "@testing-library/jest-dom/vitest";

// Initializes the translations module with real translations (defaulting to English) before
// any test renders a component. Without this, useTranslation() has no
// resources loaded and falls back to rendering raw keys (e.g.
// "passwordRules.minLength") instead of the actual English text tests
// assert against.
import "../translations/translations";

// jsdom (Vitest's test environment) has no EventSource implementation.
// useSessionEventsStream is mounted app-wide (App.tsx), so anything that
// renders the app tree while authenticated needs a global stand-in for it
// to exist at all, or the resulting ReferenceError crashes the render.
// Tests that care about its actual message/error/reconnect behavior mock
// it more specifically themselves; this is just enough surface for
// "authenticated app renders without throwing."
class MockEventSource {
    onmessage: ((event: MessageEvent) => void) | null = null;
    onerror: ((event: Event) => void) | null = null;
    close(): void {}
}

// @ts-expect-error - a minimal stand-in for tests, not a full EventSource implementation
globalThis.EventSource = MockEventSource;

// jsdom also has no ResizeObserver. Chakra's popover-positioned components
// (Select, Combobox - see LanguageToggle.tsx) use it via floating-ui to
// track their trigger's size/position while open; without this stand-in,
// opening one throws "ResizeObserver is not defined" as soon as it mounts.
class MockResizeObserver {
    observe(): void {}
    unobserve(): void {}
    disconnect(): void {}
}

globalThis.ResizeObserver = MockResizeObserver;

// jsdom also has no Element.scrollTo. Chakra's Select (LanguageToggle.tsx)
// calls it on its popover content when an item is selected, to reset scroll
// position for next open; without this stand-in, selecting any option
// throws "scrollTo is not a function".
if (!Element.prototype.scrollTo) {
    Element.prototype.scrollTo = () => {};
}
