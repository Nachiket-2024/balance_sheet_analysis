import { describe, it, expect } from 'vitest';
import { render, screen } from '@testing-library/react';

import LoadingState from '@/ui/feedback/LoadingState';

describe('LoadingState', () => {
  it('renders the given message', () => {
    render(
        <LoadingState message="Loading users..." />
    );

    expect(screen.getByText('Loading users...')).toBeInTheDocument();
  });

  it('renders different styling for fullScreen vs. container-sized (h/bg props differ)', () => {
    // Tailwind resolves to atomic CSS classes, not inline styles, so
    // className is the only observable signal fullScreen changed anything.
    const { container: fullScreenContainer } = render(
        <LoadingState message="Loading..." fullScreen />
    );
    const { container: containerSized } = render(
        <LoadingState message="Loading..." />
    );

    const fullScreenFlex = fullScreenContainer.firstElementChild as HTMLElement;
    const defaultFlex = containerSized.firstElementChild as HTMLElement;
    expect(fullScreenFlex.className === defaultFlex.className).toBe(false);
  });
});
