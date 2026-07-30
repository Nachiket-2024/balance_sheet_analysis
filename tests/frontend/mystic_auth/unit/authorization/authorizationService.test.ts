import { describe, it, expect, beforeEach } from 'vitest';
import MockAdapter from 'axios-mock-adapter';
import api from '@/api/axiosInstance';
import {
  checkPermission,
  checkBatch,
  getUserPolicies,
  getAuditLog,
} from '@/authorization/authorizationService';

const mock = new MockAdapter(api);

describe('authorizationService', () => {
  beforeEach(() => {
    mock.reset();
  });

  describe('checkPermission', () => {
    it('returns the expected single result from a one-item batch-check call', async () => {
      mock.onPost('/authorization/batch-check').reply((config) => {
        expect(JSON.parse(config.data)).toEqual({
          checks: [{ action: 'documents:view', resource_type: 'documents', resource: undefined }],
        });
        return [
          200,
          { results: [{ action: 'documents:view', resource_type: 'documents', allowed: true, denial_reason: null }] },
        ];
      });

      const result = await checkPermission('documents:view', 'documents');

      expect(result).toEqual({
        action: 'documents:view',
        resource_type: 'documents',
        allowed: true,
        denial_reason: null,
      });
    });

    it('passes the optional resource instance through for ownership/attribute conditions', async () => {
      mock.onPost('/authorization/batch-check').reply((config) => {
        const body = JSON.parse(config.data);
        expect(body.checks[0].resource).toEqual({ status: 'draft' });
        return [200, { results: [{ action: 'documents:publish', resource_type: 'documents', allowed: true, denial_reason: null }] }];
      });

      await checkPermission('documents:publish', 'documents', { status: 'draft' });
    });
  });

  describe('checkBatch', () => {
    it('handles multiple checks and returns one result per check, in order', async () => {
      mock.onPost('/authorization/batch-check').reply((config) => {
        const body = JSON.parse(config.data);
        expect(body.checks).toEqual([
          { action: 'documents:view', resource_type: 'documents', resource: undefined },
          { action: 'reports:export', resource_type: 'reports', resource: undefined },
        ]);
        return [
          200,
          {
            results: [
              { action: 'documents:view', resource_type: 'documents', allowed: true, denial_reason: null },
              { action: 'reports:export', resource_type: 'reports', allowed: false, denial_reason: 'no_matching_policy' },
            ],
          },
        ];
      });

      const results = await checkBatch([
        { action: 'documents:view', resourceType: 'documents' },
        { action: 'reports:export', resourceType: 'reports' },
      ]);

      expect(results).toHaveLength(2);
      expect(results[0].allowed).toBe(true);
      expect(results[1].allowed).toBe(false);
      expect(results[1].denial_reason).toBe('no_matching_policy');
    });
  });

  describe('getUserPolicies', () => {
    it('fetches the caller\'s own policies via GET /authorization/users/me/policies', async () => {
      const mockResponse = {
        user_email: 'test@example.com',
        policies: [
          {
            id: 1, name: 'self_service', description: 'baseline', actions: ['users:read_own'],
            resource_type: 'users', conditions: null, is_active: true,
            created_at: '2026-01-01T00:00:00Z', updated_at: '2026-01-01T00:00:00Z', created_by: 'system',
          },
        ],
      };
      mock.onGet('/authorization/users/me/policies').reply(200, mockResponse);

      const result = await getUserPolicies();

      expect(result).toEqual(mockResponse);
    });
  });

  describe('getAuditLog', () => {
    it('fetches the caller\'s own audit log via GET /authorization/audit-log/me', async () => {
      const mockResponse = [
        {
          id: 1, user_email: 'test@example.com', action: 'users:read_own', resource_type: 'users',
          resource_identifier: null, allowed: true, candidate_policy_names: ['self_service'],
          granting_policy_names: ['self_service'], failed_conditions: null, context: null,
          created_at: '2026-01-01T00:00:00Z',
        },
      ];
      mock.onGet('/authorization/audit-log/me').reply(200, mockResponse);

      const result = await getAuditLog();

      expect(result).toEqual(mockResponse);
    });
  });

  describe('error handling', () => {
    it('checkPermission rejects (does not swallow) a 401 response', async () => {
      mock.onPost('/authorization/batch-check').reply(401, { detail: 'Not authenticated' });

      await expect(checkPermission('documents:view', 'documents')).rejects.toMatchObject({
        response: { status: 401 },
      });
    });

    it('checkBatch rejects on a 422 (e.g. empty/oversized batch)', async () => {
      mock.onPost('/authorization/batch-check').reply(422, { detail: 'checks must not be empty' });

      await expect(checkBatch([])).rejects.toMatchObject({
        response: { status: 422 },
      });
    });

    it('getUserPolicies rejects on a 500', async () => {
      mock.onGet('/authorization/users/me/policies').reply(500);

      await expect(getUserPolicies()).rejects.toMatchObject({
        response: { status: 500 },
      });
    });

    it('getAuditLog rejects on a 401', async () => {
      mock.onGet('/authorization/audit-log/me').reply(401);

      await expect(getAuditLog()).rejects.toMatchObject({
        response: { status: 401 },
      });
    });

    it('checkPermission rejects on a 403 (authenticated but the batch-check endpoint itself denied)', async () => {
      mock.onPost('/authorization/batch-check').reply(403, { detail: 'Insufficient permissions' });

      await expect(checkPermission('users:read_own', 'users')).rejects.toMatchObject({
        response: { status: 403 },
      });
    });

    it('getUserPolicies rejects on a 403', async () => {
      mock.onGet('/authorization/users/me/policies').reply(403);

      await expect(getUserPolicies()).rejects.toMatchObject({
        response: { status: 403 },
      });
    });
  });
});
