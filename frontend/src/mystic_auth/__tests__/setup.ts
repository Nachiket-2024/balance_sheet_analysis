// The "/vitest" entry point (rather than the bare package) augments
// Vitest's own `expect`/Assertion types with jest-dom's matchers.
// The generic entry point targets Jest's types instead, which left
// `.not` and other chained matchers untyped under Vitest.
import "@testing-library/jest-dom/vitest";

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
