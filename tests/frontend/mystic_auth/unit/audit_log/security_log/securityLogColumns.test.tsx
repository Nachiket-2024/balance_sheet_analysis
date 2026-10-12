import { describe, it, expect } from 'vitest';
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { useTranslation } from 'react-i18next';

import DataTable from '@/ui/DataTable/DataTable';
import { getSecurityColumns } from '@/audit_log/security_log/securityLogColumns';
import type { SecurityAuditLogEntryRead } from '@/api/audit_api';

function baseEntry(overrides: Partial<SecurityAuditLogEntryRead>): SecurityAuditLogEntryRead {
  return {
    id: 1,
    user_email: 'user@example.com',
    event_type: 'login_success',
    success: true,
    ip_address: '127.0.0.1',
    user_agent: null,
    request_id: null,
    event_metadata: null,
    created_at: '2026-01-01T00:00:00Z',
    ...overrides,
  };
}

function Table({ rows }: { rows: SecurityAuditLogEntryRead[] }) {
  const { t } = useTranslation('audit_log');
  return <DataTable columns={getSecurityColumns(t, 'en')} rows={rows} rowKey={(e) => e.id} />;
}

describe('getSecurityColumns', () => {
  it('keeps IP and metadata details in the selected-row drawer instead of widening the table', () => {
    render(
      <Table
        rows={[
          baseEntry({
            event_type: 'policy_assigned',
            event_metadata: { assigned_by: 'admin@example.com', policy_name: 'user_management' },
          }),
        ]}
      />
    );

    expect(screen.queryByText('127.0.0.1')).toBeNull();
    expect(screen.queryByText('"user_management" assigned by admin@example.com')).toBeNull();
  });

  it('shows a dash with a reason tooltip for a missing user_email, instead of a wordy inline label', async () => {
    const user = userEvent.setup();
    render(<Table rows={[baseEntry({ id: 7, user_email: null, event_type: 'logout' })]} />);

    expect(screen.queryByText('Unknown user')).toBeNull();
    const dash = screen.getByText('—');
    await user.hover(dash);
    expect(await screen.findByText('No account linked: the session token had already expired')).toBeInTheDocument();
  });

  it('renders Success quietly (no badge) and Failed as a badge', () => {
    render(
      <Table
        rows={[
          baseEntry({ id: 5, success: true }),
          baseEntry({ id: 6, success: false, event_type: 'login_failure' }),
        ]}
      />
    );

    // Quiet rendering pairs the text with a check icon in the same inline span (no Badge);
    // Failed goes through Badge.tsx instead, whose root span carries font-semibold.
    expect(screen.getByText('Success').closest('span')?.querySelector('svg.lucide-check')).not.toBeNull();
    expect(screen.getByText('Failed').closest('span.font-semibold')).not.toBeNull();
  });
});
