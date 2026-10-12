import { describe, it, expect } from 'vitest';

import { buildEffectiveGrantKeySet, dedupeAgainstWildcards, grantKey, isSubsumedByWildcard, policyAddsNothingNew } from '@/policies/logic/effectiveGrants';

// These back the "hide a policy/permission that adds nothing new" filtering
// in UserPoliciesDialog and UserPermissionsDialog.

describe('grantKey', () => {
  it('joins action and resource_type into one stable key', () => {
    expect(grantKey('users:read_own', 'users')).toBe('users:read_own::users');
  });
});

describe('buildEffectiveGrantKeySet', () => {
  it('fans out each assigned policy across its own actions and resource_type', () => {
    const keys = buildEffectiveGrantKeySet(
      [{ actions: ['users:read_own', 'users:delete_own'], resource_type: 'users' }],
      []
    );
    expect(keys.has(grantKey('users:read_own', 'users'))).toBe(true);
    expect(keys.has(grantKey('users:delete_own', 'users'))).toBe(true);
    expect(keys.size).toBe(2);
  });

  it('includes direct grants alongside policy-derived keys', () => {
    const keys = buildEffectiveGrantKeySet(
      [{ actions: ['users:read_own'], resource_type: 'users' }],
      [{ action: 'users:list_all', resource_type: 'users' }]
    );
    expect(keys.has(grantKey('users:read_own', 'users'))).toBe(true);
    expect(keys.has(grantKey('users:list_all', 'users'))).toBe(true);
  });

  it('returns an empty set when the user has neither policies nor direct grants', () => {
    expect(buildEffectiveGrantKeySet([], []).size).toBe(0);
  });
});

describe('policyAddsNothingNew', () => {
  it('is true when every one of the candidate policy actions is already covered', () => {
    const keys = new Set([grantKey('users:read_own', 'users')]);
    expect(policyAddsNothingNew({ actions: ['users:read_own'], resource_type: 'users' }, keys)).toBe(true);
  });

  it('is false when the candidate grants even one action outside the covered set', () => {
    const keys = new Set([grantKey('users:read_own', 'users')]);
    expect(policyAddsNothingNew({ actions: ['users:read_own', 'users:delete_own'], resource_type: 'users' }, keys)).toBe(false);
  });

  it('is false when none of the candidate actions are covered', () => {
    const keys = new Set([grantKey('reports:view', 'reports')]);
    expect(policyAddsNothingNew({ actions: ['users:read_own'], resource_type: 'users' }, keys)).toBe(false);
  });

  it('is true for a policy with an empty actions list, vacuously', () => {
    expect(policyAddsNothingNew({ actions: [], resource_type: 'users' }, new Set())).toBe(true);
  });

  it('does not match an action covered under a different resource_type', () => {
    const keys = new Set([grantKey('read', 'reports')]);
    expect(policyAddsNothingNew({ actions: ['read'], resource_type: 'users' }, keys)).toBe(false);
  });
});

describe('dedupeAgainstWildcards', () => {
  it('drops a specific grant whose action already has a wildcard entry', () => {
    const grants = [
      { action: 'policies:read', resource_type: 'policies' },
      { action: 'policies:read', resource_type: '*' },
    ];
    expect(dedupeAgainstWildcards(grants)).toEqual([{ action: 'policies:read', resource_type: '*' }]);
  });

  it('keeps a specific grant whose action has no wildcard entry', () => {
    const grants = [{ action: 'policies:read', resource_type: 'policies' }];
    expect(dedupeAgainstWildcards(grants)).toEqual(grants);
  });

  it('honors a wildcard from a separate source list, not just the grants themselves', () => {
    const grants = [{ action: 'permissions:grant', resource_type: 'permissions' }];
    const wildcardSource = [{ action: 'permissions:grant', resource_type: '*' }];
    expect(dedupeAgainstWildcards(grants, wildcardSource)).toEqual([]);
  });
});

describe('isSubsumedByWildcard', () => {
  it('is true for a specific grant already covered by a wildcard in the source list', () => {
    const wildcardSource = [{ action: 'permissions:grant', resource_type: '*' }];
    expect(isSubsumedByWildcard({ action: 'permissions:grant', resource_type: 'permissions' }, wildcardSource)).toBe(true);
  });

  it('is false when no wildcard covers the action', () => {
    const wildcardSource = [{ action: 'users:read_own', resource_type: 'users' }];
    expect(isSubsumedByWildcard({ action: 'permissions:grant', resource_type: 'permissions' }, wildcardSource)).toBe(false);
  });

  it('is false for the wildcard grant itself, even if present in the source list', () => {
    const wildcardSource = [{ action: 'permissions:grant', resource_type: '*' }];
    expect(isSubsumedByWildcard({ action: 'permissions:grant', resource_type: '*' }, wildcardSource)).toBe(false);
  });
});
