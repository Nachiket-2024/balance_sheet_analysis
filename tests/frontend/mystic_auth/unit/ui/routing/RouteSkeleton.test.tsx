import { describe, expect, it } from 'vitest';
import { render, screen } from '@testing-library/react';

import RouteSkeleton from '@/ui/routing/RouteSkeleton';

describe('RouteSkeleton', () => {
  it('renders an accessible route loading placeholder with content blocks', () => {
    const { container } = render(<RouteSkeleton />);

    expect(screen.getByRole('status')).toHaveTextContent('Loading page...');
    expect(container.querySelectorAll('[data-slot="skeleton"]')).toHaveLength(3);
    expect(container.querySelector('[data-route-loading="true"]')).toBeInTheDocument();
  });
});
