import { describe, it, expect, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';

import FilterChips from '@/ui/filters/FilterChips';

describe('FilterChips', () => {
  it('renders one chip per active filter, and calls that chip\'s own onClear when its x is clicked', async () => {
    const onClearSearch = vi.fn();
    const onClearAction = vi.fn();
    render(
      <FilterChips
        chips={[
          { key: 'search', label: 'alice@example.com', onClear: onClearSearch },
          { key: 'action', label: 'users:read_own', onClear: onClearAction },
        ]}
        onClearAll={vi.fn()}
      />
    );

    expect(screen.getByText('alice@example.com')).toBeInTheDocument();
    expect(screen.getByText('users:read_own')).toBeInTheDocument();

    const clearButtons = screen.getAllByRole('button', { name: 'Clear filters' });
    // First two are per-chip x buttons (same aria-label as the group action, disambiguated by
    // DOM order below), the last is "Clear filters (2)".
    await userEvent.click(clearButtons[0]);
    expect(onClearSearch).toHaveBeenCalled();
    expect(onClearAction).not.toHaveBeenCalled();
  });

  it('shows the count and stays enabled once at least one chip is active', () => {
    render(
      <FilterChips chips={[{ key: 'search', label: 'alice', onClear: vi.fn() }]} onClearAll={vi.fn()} />
    );
    const clearAll = screen.getByRole('button', { name: 'Clear filters (1)' });
    expect(clearAll).toBeEnabled();
  });

  it('does not render filter controls when there are no active chips', () => {
    render(<FilterChips chips={[]} onClearAll={vi.fn()} />);
    expect(screen.queryByRole('button', { name: /Clear filters/ })).not.toBeInTheDocument();
  });

  it('calls onClearAll when Clear filters is clicked', async () => {
    const onClearAll = vi.fn();
    render(
      <FilterChips chips={[{ key: 'search', label: 'alice', onClear: vi.fn() }]} onClearAll={onClearAll} />
    );
    await userEvent.click(screen.getByRole('button', { name: 'Clear filters (1)' }));
    expect(onClearAll).toHaveBeenCalled();
  });
});
