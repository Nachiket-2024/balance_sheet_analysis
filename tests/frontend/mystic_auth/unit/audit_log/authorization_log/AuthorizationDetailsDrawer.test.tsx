import { describe, it, expect, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';

import AuthorizationDetailsDrawer from '@/audit_log/authorization_log/AuthorizationDetailsDrawer';
import type { AuthorizationAuditLogEntryRead } from '@/api/audit_api';
import { formatTimestamp } from '@/audit_log/auditLogListConfig';

function baseEntry(overrides: Partial<AuthorizationAuditLogEntryRead> = {}): AuthorizationAuditLogEntryRead {
  return {
    id: 6,
    user_email: 'user@example.com',
    action: 'policies:read',
    resource_type: 'policies',
    resource_identifier: null,
    allowed: true,
    candidate_policy_names: ['self_service', 'admin'],
    granting_policy_names: ['admin'],
    failed_conditions: null,
    context: { foo: 'bar' },
    created_at: '2026-01-01T00:00:00Z',
    ...overrides,
  };
}

function renderDrawer(overrides: Partial<React.ComponentProps<typeof AuthorizationDetailsDrawer>> = {}) {
  const onClose = vi.fn();
  const onPrevious = vi.fn();
  const onNext = vi.fn();
  const onFilterUser = vi.fn();
  const onFilterAction = vi.fn();
  const utils = render(
    <AuthorizationDetailsDrawer
      entry={baseEntry()}
      onClose={onClose}
      index={6}
      total={4557}
      onPrevious={onPrevious}
      onNext={onNext}
      canGoPrevious={true}
      canGoNext={true}
      language="en"
      onFilterUser={onFilterUser}
      onFilterAction={onFilterAction}
      {...overrides}
    />
  );
  return { ...utils, onClose, onPrevious, onNext, onFilterUser, onFilterAction };
}

describe('AuthorizationDetailsDrawer', () => {
  it('renders nothing when entry is null', () => {
    const { container } = renderDrawer({ entry: null });
    expect(container).toBeEmptyDOMElement();
  });

  it('shows the position indicator and the decision fields', () => {
    renderDrawer();
    expect(screen.getByText('6 of 4557')).toBeInTheDocument();
    expect(screen.getByText('Read policies')).toBeInTheDocument();
    expect(screen.getByText('Allowed')).toBeInTheDocument();
    expect(screen.getByText('Allowed').className).toContain('text-green-900');
    expect(screen.getByText('Audit record')).toBeInTheDocument();
    expect(screen.getByText('6')).toBeInTheDocument();
  });

  it('splits granting vs. considered-but-not-granting policies', () => {
    renderDrawer();
    expect(screen.getByText('admin')).toBeInTheDocument();
    expect(screen.getByText('self_service')).toBeInTheDocument();
  });

  it('shows Failed conditions only for a denied decision', () => {
    const { rerender } = renderDrawer({ entry: baseEntry({ allowed: true }) });
    expect(screen.queryByText('Failed conditions')).toBeNull();

    rerender(
      <AuthorizationDetailsDrawer
        entry={baseEntry({ allowed: false, failed_conditions: { region: ['must be "us"'] } })}
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
    expect(screen.getByText('Failed conditions')).toBeInTheDocument();
    expect(screen.getByText(/must be "us"/)).toBeInTheDocument();
  });

  it('shows "No policy covered this action" for a denial with no failed_conditions', () => {
    renderDrawer({ entry: baseEntry({ allowed: false, failed_conditions: null }) });
    expect(screen.getByText('No policy covered this action')).toBeInTheDocument();
  });

  it('uses red result styling for a denied decision', () => {
    renderDrawer({ entry: baseEntry({ allowed: false }) });
    expect(screen.getByText('Denied').className).toContain('bg-red-200');
  });

  it('renders the request context as readable rows', () => {
    renderDrawer({ entry: baseEntry({ context: { foo: 'bar', evaluated_at: '2026-09-21T15:11:53.448203+00:00' } }) });
    expect(screen.getByText('Foo')).toBeInTheDocument();
    expect(screen.getByText('bar')).toBeInTheDocument();
    expect(screen.getByText(formatTimestamp('2026-09-21T15:11:53.448203+00:00', 'en'))).toBeInTheDocument();
    expect(screen.queryByText('2026-09-21T15:11:53.448203+00:00')).toBeNull();
  });

  it('does not show an empty request context section', () => {
    renderDrawer({ entry: baseEntry({ context: null }) });
    expect(screen.queryByText('Request context')).toBeNull();
    expect(screen.queryByText('No request context recorded')).toBeNull();
  });

  it('calls onFilterUser/onFilterAction with the entry\'s own values when a footer shortcut is clicked', async () => {
    const user = userEvent.setup();
    const { onFilterUser, onFilterAction } = renderDrawer();

    await user.click(screen.getByRole('button', { name: 'Only this user' }));
    expect(onFilterUser).toHaveBeenCalledWith('user@example.com');

    await user.click(screen.getByRole('button', { name: 'Only this action' }));
    expect(onFilterAction).toHaveBeenCalledWith('policies:read');
  });

  it('copies the audit event ID and gives accessible copied feedback', async () => {
    const user = userEvent.setup();
    const writeText = vi.spyOn(navigator.clipboard, 'writeText');
    renderDrawer();

    const copyButtons = screen.getAllByRole('button', { name: 'Copy' });
    await user.click(copyButtons[1]);

    expect(writeText).toHaveBeenCalledWith('6');
    expect(screen.getAllByRole('button', { name: 'Copied' })).toHaveLength(1);
  });

  it('disables Previous/Next according to canGoPrevious/canGoNext', () => {
    renderDrawer({ canGoPrevious: false, canGoNext: false });
    expect(screen.getByRole('button', { name: 'Previous' })).toBeDisabled();
    expect(screen.getByRole('button', { name: 'Next' })).toBeDisabled();
  });

  it('keeps every detail section open without disclosure controls', () => {
    renderDrawer();

    expect(screen.getByText('Read policies')).toBeVisible();
    expect(screen.queryByRole('button', { name: 'Collapse all' })).toBeNull();
    expect(screen.queryByRole('button', { name: 'Expand all' })).toBeNull();
    expect(screen.queryByRole('button', { name: 'Decision' })).toBeNull();
    expect(screen.getByText('Request context')).toBeVisible();
  });
});
