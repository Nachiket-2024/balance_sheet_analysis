import { describe, it, expect, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';

import SecurityDetailsDrawer from '@/audit_log/security_log/SecurityDetailsDrawer';
import type { SecurityAuditLogEntryRead } from '@/api/audit_api';

function baseEntry(overrides: Partial<SecurityAuditLogEntryRead> = {}): SecurityAuditLogEntryRead {
  return {
    id: 9,
    user_email: 'user@example.com',
    event_type: 'login_success',
    success: true,
    ip_address: '203.0.113.7',
    user_agent: 'Mozilla/5.0 Chrome/1.0',
    request_id: 'req-abc-123',
    event_metadata: { assigned_by: 'admin@example.com' },
    created_at: '2026-01-01T00:00:00Z',
    ...overrides,
  };
}

function renderDrawer(overrides: Partial<React.ComponentProps<typeof SecurityDetailsDrawer>> = {}) {
  const onClose = vi.fn();
  const onPrevious = vi.fn();
  const onNext = vi.fn();
  const onFilterUser = vi.fn();
  const onFilterIp = vi.fn();
  const onFilterEvent = vi.fn();
  const utils = render(
    <SecurityDetailsDrawer
      entry={baseEntry()}
      onClose={onClose}
      index={1}
      total={100}
      onPrevious={onPrevious}
      onNext={onNext}
      canGoPrevious={false}
      canGoNext={true}
      language="en"
      onFilterUser={onFilterUser}
      onFilterIp={onFilterIp}
      onFilterEvent={onFilterEvent}
      {...overrides}
    />
  );
  return { ...utils, onClose, onPrevious, onNext, onFilterUser, onFilterIp, onFilterEvent };
}

describe('SecurityDetailsDrawer', () => {
  it('renders nothing when entry is null', () => {
    const { container } = renderDrawer({ entry: null });
    expect(container).toBeEmptyDOMElement();
  });

  it('shows event, client and request fields', () => {
    renderDrawer();
    expect(screen.getByText('Success').className).toContain('text-green-900');
    expect(screen.getByText('Login success')).toBeInTheDocument();
    expect(screen.getByText('203.0.113.7')).toBeInTheDocument();
    expect(screen.getByText('Mozilla/5.0 Chrome/1.0')).toBeInTheDocument();
    expect(screen.getByText('req-abc-123')).toBeInTheDocument();
  });

  it('uses red result styling for a failed security event', () => {
    renderDrawer({ entry: baseEntry({ success: false }) });
    expect(screen.getByText('Failed').className).toContain('bg-red-200');
  });

  it('shows a reasoned placeholder for a missing IP/user agent/request id', () => {
    renderDrawer({ entry: baseEntry({ ip_address: null, user_agent: null, request_id: null }) });
    expect(screen.getByText('Unknown')).toBeInTheDocument();
    expect(screen.getByText('No user agent recorded')).toBeInTheDocument();
    expect(screen.getByText('No request ID recorded')).toBeInTheDocument();
  });

  it('renders event metadata as readable rows, or a note when absent', () => {
    const { rerender } = renderDrawer();
    expect(screen.getByText('Assigned by')).toBeInTheDocument();
    expect(screen.getByText('admin@example.com')).toBeInTheDocument();

    rerender(
      <SecurityDetailsDrawer
        entry={baseEntry({ event_metadata: null })}
        onClose={vi.fn()}
        index={1}
        total={1}
        onPrevious={vi.fn()}
        onNext={vi.fn()}
        canGoPrevious={false}
        canGoNext={false}
        language="en"
      />
    );
    expect(screen.getByText('No metadata recorded for this event')).toBeInTheDocument();
  });

  it('shows account reactivation metadata without exposing raw JSON keys', () => {
    renderDrawer({
      entry: baseEntry({
        event_type: 'account_reactivated',
        event_metadata: { reactivated_by: 'nachiketk2021@gmail.com' },
      }),
    });

    expect(screen.getByText('Reactivated by')).toBeInTheDocument();
    expect(screen.getByText('Account reactivated')).toBeInTheDocument();
    expect(screen.getByText('nachiketk2021@gmail.com')).toBeInTheDocument();
    expect(screen.queryByText('reactivated_by')).toBeNull();
  });

  it('shows who changed access, who was changed, what changed, and when', () => {
    renderDrawer({
      entry: baseEntry({
        user_email: 'target@example.com',
        event_type: 'permission_granted',
        event_metadata: {
          granted_by: 'admin@example.com',
          action: 'users:deactivate_any',
          resource_type: 'users',
        },
      }),
    });

    expect(screen.getByText('Access change')).toBeInTheDocument();
    expect(screen.getByText('users:deactivate_any on users granted by admin@example.com')).toBeInTheDocument();
    expect(screen.getByText('Target user')).toBeInTheDocument();
    expect(screen.getAllByText('target@example.com').length).toBeGreaterThanOrEqual(1);
    expect(screen.getByText('Actor')).toBeInTheDocument();
    expect(screen.getAllByText('admin@example.com').length).toBeGreaterThanOrEqual(1);
    expect(screen.getAllByText('Action').length).toBeGreaterThanOrEqual(1);
    expect(screen.getAllByText('users:deactivate_any').length).toBeGreaterThanOrEqual(1);
    expect(screen.getAllByText('Resource type').length).toBeGreaterThanOrEqual(1);
    expect(screen.getAllByText('users').length).toBeGreaterThanOrEqual(1);
  });

  it('calls onFilterIp/onFilterEvent with the entry\'s own values', async () => {
    const user = userEvent.setup();
    const { onFilterIp, onFilterEvent } = renderDrawer();

    await user.click(screen.getByRole('button', { name: 'Only this IP' }));
    expect(onFilterIp).toHaveBeenCalledWith('203.0.113.7');

    await user.click(screen.getByRole('button', { name: 'Only this event' }));
    expect(onFilterEvent).toHaveBeenCalledWith('login_success');
  });

  it('omits the "Only this IP" footer shortcut when the entry has no IP', () => {
    renderDrawer({ entry: baseEntry({ ip_address: null }) });
    expect(screen.queryByRole('button', { name: 'Only this IP' })).toBeNull();
  });

  it('formats boolean, scalar, array, and nested metadata values', () => {
    renderDrawer({
      entry: baseEntry({
        event_metadata: {
          confirmed: true,
          attempts: 2,
          scopes: ['users:read', 'users:write'],
          nested: { old_role: 'user', new_role: 'admin' },
          empty: [],
        },
      }),
    });

    expect(screen.getByText('Yes')).toBeInTheDocument();
    expect(screen.getByText('2')).toBeInTheDocument();
    expect(screen.getByText('users:read, users:write')).toBeInTheDocument();
    expect(screen.getByText(/Old role: user/)).toBeInTheDocument();
    expect(screen.getByText('-')).toBeInTheDocument();
  });

  it('copies an IP and invokes navigation and user filters', async () => {
    const user = userEvent.setup();
    const { onClose, onPrevious, onNext, onFilterUser } = renderDrawer({ canGoPrevious: true });

    await user.click(screen.getByRole('button', { name: 'Copy' }));
    await user.click(screen.getByRole('button', { name: 'Previous' }));
    await user.click(screen.getByRole('button', { name: 'Next' }));
    await user.click(screen.getByRole('button', { name: 'Only this user' }));
    await user.click(screen.getByRole('button', { name: 'Close dialog' }));

    expect(onPrevious).toHaveBeenCalled();
    expect(onNext).toHaveBeenCalled();
    expect(onFilterUser).toHaveBeenCalledWith('user@example.com');
    expect(onClose).toHaveBeenCalled();
  });
});
