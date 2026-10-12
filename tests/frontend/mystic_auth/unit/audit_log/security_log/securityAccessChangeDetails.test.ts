import { describe, expect, it, vi } from 'vitest';
import type { TFunction } from 'i18next';

import {
  securityAccessChangeDetails,
  securityAccessChangeSummary,
} from '@/audit_log/security_log/securityAccessChangeDetails';

const t = vi.fn((key: string, values?: Record<string, unknown>) =>
  values ? `${key}:${JSON.stringify(values)}` : key
) as unknown as TFunction<'audit_log'>;

function entry(event_type: string, event_metadata?: Record<string, unknown>, user_email = 'target@example.com') {
  return { event_type, event_metadata, user_email } as never;
}

describe('security access change details', () => {
  it.each([
    ['policy_assigned', ['assigned_by', 'policy_name']],
    ['policy_revoked', ['revoked_by', 'policy_name']],
    ['policy_action_revoked', ['revoked_by', 'policy_name', 'action']],
    ['permission_granted', ['granted_by', 'action', 'resource_type']],
    ['permission_revoked', ['revoked_by', 'action', 'resource_type']],
    ['user_role_changed', ['changed_by', 'old_role', 'new_role']],
  ])('returns target, actor, and fields for %s', (eventType, keys) => {
    const metadata = Object.fromEntries(keys.map((key) => [key, `${key}-value`]));
    const details = securityAccessChangeDetails(entry(eventType, metadata), t);

    expect(details.map((item) => item.value)).toEqual(['target@example.com', ...keys.map((key) => `${key}-value`)]);
    expect(securityAccessChangeSummary(entry(eventType, metadata), t)).toContain(
      eventType === 'policy_assigned' ? 'policyAssigned' :
        eventType === 'policy_revoked' ? 'policyRevoked' :
          eventType === 'policy_action_revoked' ? 'policyActionRevoked' :
            eventType === 'permission_granted' ? 'permissionGranted' :
              eventType === 'permission_revoked' ? 'permissionRevoked' : 'roleChanged'
    );
  });

  it('handles missing metadata, blank values, missing target, and unknown event types', () => {
    expect(securityAccessChangeDetails(entry('policy_assigned'), t).length).toBe(0);
    expect(securityAccessChangeDetails(entry('unknown', { assigned_by: ' ', policy_name: '' }), t)).toEqual([]);
    expect(securityAccessChangeSummary(entry('unknown', { value: 'x' }), t)).toBeNull();
    expect(securityAccessChangeDetails(entry('policy_assigned', { assigned_by: 'admin' }, ''), t)).toEqual([
      { label: 'security.drawer.actor', value: 'admin' },
    ]);
  });
});
