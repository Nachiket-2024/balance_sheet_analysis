import { describe, it, expect, vi, afterEach } from 'vitest';
import { render, screen } from '@testing-library/react';
import { ChakraProvider, defaultSystem } from '@chakra-ui/react';

// Mocked so these tests exercise ErrorBoundary's own catch-and-render
// behavior without depending on VITE_SENTRY_DSN or the real @sentry/react
// SDK. reportError itself has its own dedicated coverage in
// core/errorMonitoring.test.ts.
vi.mock('@/core/errorMonitoring', () => ({
  reportError: vi.fn(),
}));

import ErrorBoundary from '@/ui/ErrorBoundary';
import { reportError } from '@/core/errorMonitoring';

const Bomb: React.FC = () => {
  throw new Error('boom');
};

describe('ErrorBoundary', () => {
  afterEach(() => {
    vi.restoreAllMocks();
    // restoreAllMocks doesn't clear a manually-created vi.fn() from a
    // vi.mock() factory (only vi.spyOn spies), so without this, call counts
    // from earlier tests in this file (several of which also render
    // <Bomb />) would accumulate onto this mock across tests.
    vi.mocked(reportError).mockClear();
  });

  it('renders children normally when nothing below it throws', () => {
    render(
      <ChakraProvider value={defaultSystem}>
        <ErrorBoundary>
          <div>Everything is fine</div>
        </ErrorBoundary>
      </ChakraProvider>
    );

    expect(screen.getByText('Everything is fine')).toBeInTheDocument();
  });

  it('renders the fallback instead of crashing the whole tree when a child throws during render', () => {
    // React logs the error to the console on its own in addition to
    // componentDidCatch, silenced here so the test's own output stays
    // readable; the assertions below are what actually prove the boundary
    // caught it, not the absence of a console line.
    vi.spyOn(console, 'error').mockImplementation(() => {});

    render(
      <ChakraProvider value={defaultSystem}>
        <ErrorBoundary>
          <Bomb />
        </ErrorBoundary>
      </ChakraProvider>
    );

    expect(screen.getByText('Something went wrong')).toBeInTheDocument();
    // .not.toBeInTheDocument() doesn't type-check here, see
    // docs/mystic_auth/testing/overview.md's ".not chaining" note: toBeNull() on
    // queryByText's result is the positive-assertion equivalent.
    expect(screen.queryByText('Everything is fine')).toBeNull();
  });

  it('offers a reload action in the fallback', () => {
    vi.spyOn(console, 'error').mockImplementation(() => {});

    render(
      <ChakraProvider value={defaultSystem}>
        <ErrorBoundary>
          <Bomb />
        </ErrorBoundary>
      </ChakraProvider>
    );

    expect(screen.getByRole('button', { name: 'Reload' })).toBeInTheDocument();
  });

  it('reports the caught error for error monitoring', () => {
    vi.spyOn(console, 'error').mockImplementation(() => {});

    render(
      <ChakraProvider value={defaultSystem}>
        <ErrorBoundary>
          <Bomb />
        </ErrorBoundary>
      </ChakraProvider>
    );

    expect(reportError).toHaveBeenCalledOnce();
    const [reportedError] = vi.mocked(reportError).mock.calls[0];
    expect((reportedError as Error).message).toBe('boom');
  });
});
