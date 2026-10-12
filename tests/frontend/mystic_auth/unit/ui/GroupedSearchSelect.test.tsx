import { describe, it, expect, vi } from 'vitest';
import { render, screen, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';

import GroupedSearchSelect, { type GroupedSearchOptionGroup } from '@/ui/filters/GroupedSearchSelect';

const GROUPS: GroupedSearchOptionGroup[] = [
  {
    key: 'users',
    label: 'users',
    options: [
      { value: 'users:read_own', label: 'users:read_own' },
      { value: 'users:list_all', label: 'users:list_all' },
    ],
  },
  {
    key: 'policies',
    label: 'policies',
    options: [{ value: 'policies:read', label: 'policies:read' }],
  },
];

function renderPicker(props: Partial<React.ComponentProps<typeof GroupedSearchSelect>> = {}) {
  const onChange = vi.fn();
  const onSelectGroup = vi.fn();
  const utils = render(
    <GroupedSearchSelect
      value=""
      onChange={onChange}
      groups={GROUPS}
      allValue=""
      allLabel="All actions"
      ariaLabel="Filter by action"
      searchPlaceholder="Search actions..."
      isActive={false}
      onSelectGroup={onSelectGroup}
      {...props}
    />
  );
  return { ...utils, onChange, onSelectGroup };
}

describe('GroupedSearchSelect', () => {
  it('shows the trigger with the All label until a real option is picked', () => {
    renderPicker();
    expect(screen.getByRole('button', { name: 'Filter by action' })).toHaveTextContent('All actions');
  });

  it('lists every option grouped under its own group header', async () => {
    renderPicker();
    await userEvent.click(screen.getByRole('button', { name: 'Filter by action' }));

    expect(screen.getByText('users')).toBeInTheDocument();
    expect(screen.getByText('policies')).toBeInTheDocument();
    expect(screen.getByText('users:read_own')).toBeInTheDocument();
    expect(screen.getByText('policies:read')).toBeInTheDocument();
  });

  it('narrows visible options across every group when searching', async () => {
    renderPicker();
    await userEvent.click(screen.getByRole('button', { name: 'Filter by action' }));
    await userEvent.type(screen.getByPlaceholderText('Search actions...'), 'read');

    expect(screen.getByText('users:read_own')).toBeInTheDocument();
    expect(screen.getByText('policies:read')).toBeInTheDocument();
    expect(screen.queryByText('users:list_all')).toBeNull();
  });

  it('shows a no-matches message when the query matches nothing', async () => {
    renderPicker();
    await userEvent.click(screen.getByRole('button', { name: 'Filter by action' }));
    await userEvent.type(screen.getByPlaceholderText('Search actions...'), 'nonexistent-query');

    expect(screen.getByText('No matches')).toBeInTheDocument();
  });

  it('calls onChange and closes the popover when an option is clicked', async () => {
    const { onChange } = renderPicker();
    await userEvent.click(screen.getByRole('button', { name: 'Filter by action' }));
    await userEvent.click(screen.getByText('policies:read'));

    expect(onChange).toHaveBeenCalledWith('policies:read');
    expect(screen.queryByPlaceholderText('Search actions...')).toBeNull();
  });

  it('calls onSelectGroup (and not onChange) when a group header is clicked', async () => {
    const { onChange, onSelectGroup } = renderPicker();
    await userEvent.click(screen.getByRole('button', { name: 'Filter by action' }));
    await userEvent.click(screen.getByRole('button', { name: 'users' }));

    expect(onSelectGroup).toHaveBeenCalledWith('users');
    expect(onChange).not.toHaveBeenCalled();
  });

  it('selects the highlighted option on Enter after arrowing down', async () => {
    const { onChange } = renderPicker();
    await userEvent.click(screen.getByRole('button', { name: 'Filter by action' }));

    const input = screen.getByPlaceholderText('Search actions...');
    // Flattened order is users:read_own, users:list_all, policies:read -
    // three ArrowDowns from the neutral opening state lands on policies:read.
    await userEvent.type(input, '{ArrowDown}{ArrowDown}{ArrowDown}{Enter}');

    expect(onChange).toHaveBeenCalledWith('policies:read');
  });

  it('shows the sublabel (raw code) under a translated label when given', async () => {
    renderPicker({
      groups: [
        { key: 'signIn', label: 'Sign-in', options: [{ value: 'login', label: 'Signed in', sublabel: 'login' }] },
      ],
    });
    await userEvent.click(screen.getByRole('button', { name: 'Filter by action' }));

    const option = screen.getByText('Signed in').closest('button')!;
    expect(within(option).getByText('login')).toBeInTheDocument();
  });
});
