import { describe, it, expect, beforeEach } from 'vitest';
import MockAdapter from 'axios-mock-adapter';
import api from '@/api/axiosInstance';
import { getCurrentUserApi } from '@/api/auth_api';

const mock = new MockAdapter(api);

describe('getCurrentUserApi', () => {
  beforeEach(() => {
    mock.reset();
  });

  it('should send GET request to /auth/me with the caller source as a query param', async () => {
    const mockResponse = { name: 'Test User', email: 'test@example.com', role: 'user' };

    mock.onGet('/auth/me').reply((config) => {
      expect(config.params).toEqual({ src: 'DashboardPage' });
      return [200, mockResponse];
    });

    const response = await getCurrentUserApi('DashboardPage');
    expect(response.status).toBe(200);
    expect(response.data).toEqual(mockResponse);
  });

  it('should default the source param to "unknown" when not provided', async () => {
    mock.onGet('/auth/me').reply((config) => {
      expect(config.params).toEqual({ src: 'unknown' });
      return [200, { name: 'Test User', email: 'test@example.com', role: 'user' }];
    });

    await getCurrentUserApi();
  });

  it('should reject with 401 when there is no valid access token cookie', async () => {
    mock.onGet('/auth/me').reply(401, { detail: 'Not authenticated' });

    await expect(getCurrentUserApi('DashboardPage')).rejects.toMatchObject({
      response: { status: 401 },
    });
  });

  it('should reject with 403 when the account has been deactivated', async () => {
    mock.onGet('/auth/me').reply(403);

    await expect(getCurrentUserApi('DashboardPage')).rejects.toMatchObject({
      response: { status: 403 },
    });
  });
});
