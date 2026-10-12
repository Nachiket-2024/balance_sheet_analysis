import { describe, it, expect } from 'vitest';
import { render, screen } from '@testing-library/react';
import { useTranslation } from 'react-i18next';

import DataTable from '@/ui/DataTable/DataTable';
import { getAuthorizationColumns } from '@/audit_log/authorization_log/authorizationLogColumns';
import type { AuthorizationAuditLogEntryRead } from '@/api/audit_api';

function baseEntry(overrides: Partial<AuthorizationAuditLogEntryRead>): AuthorizationAuditLogEntryRead {
  return {
    id: 1,
    user_email: 'user@example.com',
    action: 'users:read_own',
    resource_type: 'users',
    resource_identifier: null,
    allowed: true,
    candidate_policy_names: [],
    granting_policy_names: [],
    failed_conditions: null,
    context: null,
    created_at: '2026-01-01T00:00:00Z',
    ...overrides,
  };
}

function Table({ rows }: { rows: AuthorizationAuditLogEntryRead[] }) {
  const { t } = useTranslation('audit_log');
  return <DataTable columns={getAuthorizationColumns(t, 'en')} rows={rows} rowKey={(e) => e.id} />;
}

describe('getAuthorizationColumns', () => {
  it('renders Allowed quietly (no badge) and Denied as a badge', () => {
    render(
      <Table
        rows={[
          baseEntry({ id: 1, allowed: true }),
          baseEntry({ id: 2, allowed: false, action: 'users:list_all' }),
        ]}
      />
    );

    // Quiet rendering pairs the text with a check icon in the same inline span (no Badge);
    // Denied goes through Badge.tsx instead, whose root span carries font-semibold.
    expect(screen.getByText('Allowed').closest('span')?.querySelector('svg.lucide-check')).not.toBeNull();
    expect(screen.getByText('Denied').closest('span.font-semibold')).not.toBeNull();
  });

  it('shows the resource identifier under the resource type and omits a placeholder when absent', () => {
    render(
      <Table
        rows={[
          baseEntry({ id: 3, resource_type: 'users', resource_identifier: 'user_42' }),
          baseEntry({ id: 4, resource_type: 'policies', resource_identifier: null }),
        ]}
      />
    );

    expect(screen.getByText('user_42')).toBeInTheDocument();
    expect(screen.getByText('Policies')).toBeInTheDocument();
    expect(screen.queryByText('—')).toBeNull();
    expect(screen.queryByText('Not tied to a single record')).toBeNull();
  });
});
