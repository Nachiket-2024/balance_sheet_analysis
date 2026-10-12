import { describe, it, expect, beforeEach } from 'vitest';
import MockAdapter from 'axios-mock-adapter';
import api from '@/api/axiosInstance';
import { listRateLimitsApi, resetRateLimitApi } from '@/api/rate_limits_api';

const mock = new MockAdapter(api);

beforeEach(() => {
  mock.reset();
});

describe('listRateLimitsApi', () => {
  it('sends a GET request to /rate-limits/ with page/scope/endpoint params', async () => {
    mock.onGet('/rate-limits/').reply((config) => {
      expect(config.params).toMatchObject({ page: 5, scope: 'ip', endpoint: 'login', page_size: 50, kind: 'at_limit', sort_by: 'count', sort_dir: 'desc' });
      return [200, { entries: [], total: 0, truncated: false }];
    });

    const response = await listRateLimitsApi({ page: 5, scope: 'ip', endpoint: 'login', pageSize: 50, kind: 'at_limit', sortBy: 'count', sortDir: 'desc' });

    expect(response.data).toEqual({ entries: [], total: 0, truncated: false });
  });

  it('defaults page to 1 when omitted', async () => {
    mock.onGet('/rate-limits/').reply((config) => {
      expect(config.params.page).toBe(1);
      return [200, { entries: [], total: 0, truncated: false }];
    });

    await listRateLimitsApi();
  });

  it('propagates a 403 when the caller lacks rate_limits:read', async () => {
    mock.onGet('/rate-limits/').reply(403, { detail: 'Forbidden' });

    await expect(listRateLimitsApi()).rejects.toMatchObject({ response: { status: 403 } });
  });

  it('passes scope "email" through unchanged (login_lock:email:* lockout counters)', async () => {
    mock.onGet('/rate-limits/').reply((config) => {
      expect(config.params).toMatchObject({ scope: 'email' });
      return [200, { entries: [], total: 0, truncated: false }];
    });

    await listRateLimitsApi({ scope: 'email' });
  });
});

describe('resetRateLimitApi', () => {
  it('URL-encodes the raw Valkey key (which contains colons) in the path', async () => {
    const key = 'login:ip:203.0.113.5';
    mock.onDelete(`/rate-limits/${encodeURIComponent(key)}`).reply(204);

    const response = await resetRateLimitApi(key);

    expect(response.status).toBe(204);
  });

  it('propagates a 403 when the caller lacks rate_limits:reset', async () => {
    const key = 'login:ip:203.0.113.5';
    mock.onDelete(`/rate-limits/${encodeURIComponent(key)}`).reply(403, { detail: 'Forbidden' });

    await expect(resetRateLimitApi(key)).rejects.toMatchObject({ response: { status: 403 } });
  });
});
