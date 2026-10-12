import { describe, it, expect, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';

import SecurityFilterBar from '@/audit_log/security_log/SecurityFilterBar';
import { DEFAULT_TIME_RANGE_STATE } from '@/audit_log/auditLogListConfig';

function renderBar(overrides: Partial<React.ComponentProps<typeof SecurityFilterBar>> = {}) {
  const setEventType = vi.fn();
  const setIpAddress = vi.fn();
  const setSuccess = vi.fn();
  const utils = render(
    <SecurityFilterBar
      timeRange={DEFAULT_TIME_RANGE_STATE}
      setTimeRange={vi.fn()}
      search=""
      setSearch={vi.fn()}
      mine={false}
      eventType=""
      setEventType={setEventType}
      ipAddress=""
      setIpAddress={setIpAddress}
      success=""
      setSuccess={setSuccess}
      chips={[]}
      onClearAll={vi.fn()}
      isFetching={false}
      totalResults={undefined}
      {...overrides}
    />
  );
  return { ...utils, setEventType, setIpAddress, setSuccess };
}

describe('SecurityFilterBar', () => {
  it('groups the Event picker into Sign-in/Sessions/Account/Password/Access changes', async () => {
    renderBar();
    await userEvent.click(screen.getByRole('button', { name: 'Filter by event' }));

    expect(screen.getByText('Sign-in')).toBeInTheDocument();
    expect(screen.getByText('Sessions')).toBeInTheDocument();
    expect(screen.getByText('Account')).toBeInTheDocument();
    expect(screen.getByText('Password')).toBeInTheDocument();
    expect(screen.getByText('Access changes')).toBeInTheDocument();
  });

  it('shows a translated label with the raw event code beneath it', async () => {
    renderBar();
    await userEvent.click(screen.getByRole('button', { name: 'Filter by event' }));

    const option = screen.getByText('Signed in').closest('button')!;
    expect(option).toHaveTextContent('login');
  });

  it('picking an event sets the event filter to the raw event_type value', async () => {
    const { setEventType } = renderBar();
    await userEvent.click(screen.getByRole('button', { name: 'Filter by event' }));
    await userEvent.click(screen.getByText('Policy assigned'));

    expect(setEventType).toHaveBeenCalledWith('policy_assigned');
  });
});
