import React, { Suspense } from 'react';
import { describe, it, expect, beforeEach } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';

import { useRouteLoadingStore } from '@/store/routeLoadingStore';
import { trackedLazy } from '@/ui/routing/trackedLazy';

// Minimal error boundary so the rejection test doesn't crash the render
// tree; trackedLazy only needs to run finishRouteLoad on failure, not
// actually recover the UI.
class TestErrorBoundary extends React.Component<{ children: React.ReactNode }, { hasError: boolean }> {
  state = { hasError: false };
  static getDerivedStateFromError() {
    return { hasError: true };
  }
  render() {
    return this.state.hasError ? <div>Failed to load</div> : this.props.children;
  }
}

describe('trackedLazy', () => {
  beforeEach(() => {
    useRouteLoadingStore.setState({ pendingCount: 0 });
  });

  it('calls startRouteLoad as soon as the lazy component suspends, before the import resolves', async () => {
    let resolveImport!: () => void;
    const LazyComp = trackedLazy(
      () =>
        new Promise<{ default: React.ComponentType }>((resolve) => {
          resolveImport = () => resolve({ default: () => <div>Loaded</div> });
        })
    );

    render(
      <Suspense fallback={<div>Loading...</div>}>
        <LazyComp />
      </Suspense>
    );

    expect(screen.getByText('Loading...')).toBeInTheDocument();
    expect(useRouteLoadingStore.getState().pendingCount).toBe(1);

    resolveImport();
    await waitFor(() => expect(screen.getByText('Loaded')).toBeInTheDocument());
  });

  it('calls finishRouteLoad once the import resolves successfully', async () => {
    let resolveImport!: () => void;
    const LazyComp = trackedLazy(
      () =>
        new Promise<{ default: React.ComponentType }>((resolve) => {
          resolveImport = () => resolve({ default: () => <div>Loaded</div> });
        })
    );

    render(
      <Suspense fallback={<div>Loading...</div>}>
        <LazyComp />
      </Suspense>
    );

    resolveImport();
    await waitFor(() => expect(screen.getByText('Loaded')).toBeInTheDocument());

    expect(useRouteLoadingStore.getState().pendingCount).toBe(0);
  });

  it('still calls finishRouteLoad when the import rejects (failure case)', async () => {
    let rejectImport!: (err: Error) => void;
    const LazyComp = trackedLazy(
      () =>
        new Promise<{ default: React.ComponentType }>((_resolve, reject) => {
          rejectImport = reject;
        })
    );

    render(
      <TestErrorBoundary>
        <Suspense fallback={<div>Loading...</div>}>
          <LazyComp />
        </Suspense>
      </TestErrorBoundary>
    );

    expect(useRouteLoadingStore.getState().pendingCount).toBe(1);

    rejectImport(new Error('chunk load failed'));
    await waitFor(() => expect(screen.getByText('Failed to load')).toBeInTheDocument());

    expect(useRouteLoadingStore.getState().pendingCount).toBe(0);
  });
});
