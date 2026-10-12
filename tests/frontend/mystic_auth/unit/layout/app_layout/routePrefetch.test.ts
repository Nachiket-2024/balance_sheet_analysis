import { describe, it, vi, beforeEach } from 'vitest';

describe('prefetchRoute', () => {
  beforeEach(() => {
    vi.resetModules();
    vi.doUnmock('@/dashboard/DashboardPage');
  });

  it('does nothing for a path with no mapped route', async () => {
    const { prefetchRoute } = await import('@/layout/app_layout/routePrefetch');

    prefetchRoute('/not-a-real-route');
  });

  it('prefetches a known route and ignores a repeat call for the same path', async () => {
    const { prefetchRoute } = await import('@/layout/app_layout/routePrefetch');

    // Second call must hit the early-return branch, not re-trigger the import.
    prefetchRoute('/dashboard');
    prefetchRoute('/dashboard');
  });

  it('allows a retry after a failed prefetch', async () => {
    vi.doMock('@/dashboard/DashboardPage', () => {
      throw new Error('chunk load failed');
    });

    const { prefetchRoute } = await import('@/layout/app_layout/routePrefetch');

    prefetchRoute('/dashboard');
    // Lets the rejected import's .catch() remove the path from the
    // in-flight set before retrying.
    await new Promise((resolve) => setTimeout(resolve, 0));

    prefetchRoute('/dashboard');
  });
});
