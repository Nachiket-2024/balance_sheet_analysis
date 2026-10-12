import { describe, it, expect, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';

import AuthorizationFilterBar from '@/audit_log/authorization_log/AuthorizationFilterBar';
import { DEFAULT_TIME_RANGE_STATE } from '@/audit_log/auditLogListConfig';

function renderBar(overrides: Partial<React.ComponentProps<typeof AuthorizationFilterBar>> = {}) {
  const setAction = vi.fn();
  const setResourceType = vi.fn();
  const setAllowed = vi.fn();
  const utils = render(
    <AuthorizationFilterBar
      timeRange={DEFAULT_TIME_RANGE_STATE}
      setTimeRange={vi.fn()}
      search=""
      setSearch={vi.fn()}
      mine={false}
      action=""
      setAction={setAction}
      resourceType=""
      setResourceType={setResourceType}
      allowed=""
      setAllowed={setAllowed}
      chips={[]}
      onClearAll={vi.fn()}
      isFetching={false}
      totalResults={undefined}
      {...overrides}
    />
  );
  return { ...utils, setAction, setResourceType, setAllowed };
}

describe('AuthorizationFilterBar', () => {
  it('groups the Action picker by resource type, from PERMISSIONS', async () => {
    renderBar();
    await userEvent.click(screen.getByRole('button', { name: 'Filter by action' }));

    expect(screen.getByText('Users')).toBeInTheDocument();
    expect(screen.getByText('Policies')).toBeInTheDocument();
    expect(screen.getByText('Read own users')).toBeInTheDocument();
  });

  it('clicking a group header sets the resource type filter and clears the action filter, with no separate resource dropdown', async () => {
    const { setResourceType, setAction } = renderBar();
    await userEvent.click(screen.getByRole('button', { name: 'Filter by action' }));
    await userEvent.click(screen.getByRole('button', { name: 'Policies' }));

    expect(setResourceType).toHaveBeenCalledWith('policies');
    expect(setAction).toHaveBeenCalledWith('');
    expect(screen.queryByRole('combobox', { name: 'Filter by resource type' })).toBeNull();
  });

  it('shows "All <resource> actions" in the trigger once a resource type is set with no single action', async () => {
    renderBar({ resourceType: 'policies' });
    expect(screen.getByRole('button', { name: 'Filter by action' })).toHaveTextContent('All Policies actions');
  });

  it('extraActions/extraResourceTypes extend the grouped picker with fork-added values', async () => {
    renderBar({ extraResourceTypes: ['widgets'], extraActions: ['widgets:spin'] });
    await userEvent.click(screen.getByRole('button', { name: 'Filter by action' }));

    expect(screen.getByText('Widgets')).toBeInTheDocument();
    expect(screen.getByText('Spin widgets')).toBeInTheDocument();
  });
});
