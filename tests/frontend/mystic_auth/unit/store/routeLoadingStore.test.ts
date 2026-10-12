import { describe, it, expect, beforeEach } from 'vitest';

import { useRouteLoadingStore, startRouteLoad, finishRouteLoad } from '@/store/routeLoadingStore';

describe('routeLoadingStore', () => {
  beforeEach(() => {
    useRouteLoadingStore.setState({ pendingCount: 0 });
  });

  it('starts at 0', () => {
    expect(useRouteLoadingStore.getState().pendingCount).toBe(0);
  });

  it('increments on startRouteLoad and decrements on finishRouteLoad', () => {
    startRouteLoad();
    expect(useRouteLoadingStore.getState().pendingCount).toBe(1);

    finishRouteLoad();
    expect(useRouteLoadingStore.getState().pendingCount).toBe(0);
  });

  it('tracks multiple concurrent loads independently', () => {
    startRouteLoad();
    startRouteLoad();
    expect(useRouteLoadingStore.getState().pendingCount).toBe(2);

    finishRouteLoad();
    expect(useRouteLoadingStore.getState().pendingCount).toBe(1);

    finishRouteLoad();
    expect(useRouteLoadingStore.getState().pendingCount).toBe(0);
  });

  it('never goes negative when finishRouteLoad is called more times than startRouteLoad', () => {
    startRouteLoad();
    finishRouteLoad();
    finishRouteLoad();
    finishRouteLoad();

    expect(useRouteLoadingStore.getState().pendingCount).toBe(0);
  });
});
