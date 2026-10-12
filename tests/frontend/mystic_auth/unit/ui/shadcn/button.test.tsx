import { describe, expect, it } from 'vitest';
import { render, screen } from '@testing-library/react';

import { Button } from '@/ui/shadcn/button';

describe('Button', () => {
  it('renders variant and size data attributes and merges a custom class', () => {
    render(
      <Button variant="default" size="lg" className="custom-action">
        Save
      </Button>
    );

    const button = screen.getByRole('button', { name: 'Save' });
    expect(button).toHaveAttribute('data-slot', 'button');
    expect(button).toHaveAttribute('data-variant', 'default');
    expect(button).toHaveAttribute('data-size', 'lg');
    expect(button).toHaveClass('custom-action');
  });

  it('renders non-button children through Radix Slot when asChild is set', () => {
    render(
      <Button asChild variant="ghost">
        <a href="/settings">Settings</a>
      </Button>
    );

    const link = screen.getByRole('link', { name: 'Settings' });
    expect(link).toHaveAttribute('href', '/settings');
    expect(link).toHaveAttribute('data-slot', 'button');
    expect(link).toHaveAttribute('data-variant', 'ghost');
  });
});
