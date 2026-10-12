import { describe, it, expect } from 'vitest';

import { isDestructiveAction } from '@/authorization/destructiveActions';

describe('isDestructiveAction', () => {
  it('flags the full resource-prefixed destructive actions', () => {
    expect(isDestructiveAction('users:deactivate_any')).toBe(true);
    expect(isDestructiveAction('users:delete_any')).toBe(true);
    expect(isDestructiveAction('users:assign_system_role')).toBe(true);
    expect(isDestructiveAction('policies:delete')).toBe(true);
    expect(isDestructiveAction('policies:revoke')).toBe(true);
    expect(isDestructiveAction('permissions:revoke')).toBe(true);
    expect(isDestructiveAction('rate_limits:reset')).toBe(true);
  });

  it('does not flag a bare verb with no resource prefix', () => {
    // Every real action is resource-prefixed (see permissions.ts); a bare
    // "delete_any" never actually occurs, and matching it would be a no-op
    // that masks the set being wrong.
    expect(isDestructiveAction('delete_any')).toBe(false);
  });

  it('does not flag a merely-reversible action that shares a verb', () => {
    expect(isDestructiveAction('users:reactivate')).toBe(false);
  });

  it('does not flag ordinary read/write actions', () => {
    expect(isDestructiveAction('users:read_own')).toBe(false);
    expect(isDestructiveAction('policies:create')).toBe(false);
  });
});
