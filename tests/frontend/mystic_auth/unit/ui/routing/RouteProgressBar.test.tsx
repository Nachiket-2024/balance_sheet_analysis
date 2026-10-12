import { describe, it, expect, beforeEach } from 'vitest';
import { render, screen, act } from '@testing-library/react';

import { useRouteLoadingStore, startRouteLoad, finishRouteLoad } from '@/store/routeLoadingStore';
import RouteProgressBar from '@/ui/routing/RouteProgressBar';

function renderBar() {
  return render(
      <RouteProgressBar />
  );
}

describe('RouteProgressBar', () => {
  beforeEach(() => {
    useRouteLoadingStore.setState({ pendingCount: 0 });
  });

  it('renders nothing while pendingCount is 0', () => {
    renderBar();

    expect(screen.queryByRole('progressbar')).toBeNull();
  });

  it('shows the bar once a route load starts (pendingCount > 0)', () => {
    startRouteLoad();
    renderBar();

    expect(screen.getByRole('progressbar')).toBeInTheDocument();
  });

  it('hides the bar again once the load finishes (pendingCount back to 0)', () => {
    startRouteLoad();
    renderBar();
    expect(screen.getByRole('progressbar')).toBeInTheDocument();

    act(() => finishRouteLoad());

    expect(screen.queryByRole('progressbar')).toBeNull();
  });

  it('stays visible while a second concurrent load is still pending', () => {
    startRouteLoad();
    startRouteLoad();
    renderBar();

    act(() => finishRouteLoad());

    expect(screen.getByRole('progressbar')).toBeInTheDocument();
  });
});
