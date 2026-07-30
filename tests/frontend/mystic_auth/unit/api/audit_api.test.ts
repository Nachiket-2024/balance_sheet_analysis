import { describe, it, expect, beforeEach } from 'vitest';
import MockAdapter from 'axios-mock-adapter';
import api from '@/api/axiosInstance';
import {
  getAuthorizationAuditLogApi,
  getMyAuthorizationAuditLogApi,
  getUserAuthorizationAuditLogApi,
  getSecurityAuditLogApi,
  getMySecurityAuditLogApi,
} from '@/api/audit_api';

const mock = new MockAdapter(api);

beforeEach(() => {
  mock.reset();
});

describe('getAuthorizationAuditLogApi', () => {
  it('sends a GET request to /authorization/audit-log with default limit/offset', async () => {
    mock.onGet('/authorization/audit-log').reply((config) => {
      expect(config.params).toEqual({ limit: 50, offset: 0 });
      return [200, []];
    });

    const response = await getAuthorizationAuditLogApi();

    expect(response.status).toBe(200);
  });

  it('passes explicit limit/offset through', async () => {
    mock.onGet('/authorization/audit-log').reply((config) => {
      expect(config.params).toEqual({ limit: 5, offset: 15 });
      return [200, []];
    });

    await getAuthorizationAuditLogApi(5, 15);
  });
});

describe('getMyAuthorizationAuditLogApi', () => {
  it('sends a GET request to /authorization/audit-log/me', async () => {
    mock.onGet('/authorization/audit-log/me').reply(200, []);

    const response = await getMyAuthorizationAuditLogApi();

    expect(response.status).toBe(200);
  });
});

describe('getUserAuthorizationAuditLogApi', () => {
  it('URL-encodes the target user email in the path', async () => {
    const email = 'user+tag@example.com';
    mock.onGet(`/authorization/audit-log/users/${encodeURIComponent(email)}`).reply(200, []);

    const response = await getUserAuthorizationAuditLogApi(email);

    expect(response.status).toBe(200);
  });
});

describe('getSecurityAuditLogApi', () => {
  it('sends a GET request to /audit/security-log', async () => {
    mock.onGet('/audit/security-log').reply(200, []);

    const response = await getSecurityAuditLogApi();

    expect(response.status).toBe(200);
  });

  it('propagates a 403 when the caller lacks the security audit permission', async () => {
    mock.onGet('/audit/security-log').reply(403, { detail: 'Forbidden' });

    await expect(getSecurityAuditLogApi()).rejects.toMatchObject({ response: { status: 403 } });
  });
});

describe('getMySecurityAuditLogApi', () => {
  it('sends a GET request to /audit/security-log/me', async () => {
    mock.onGet('/audit/security-log/me').reply(200, []);

    const response = await getMySecurityAuditLogApi();

    expect(response.status).toBe(200);
  });
});
