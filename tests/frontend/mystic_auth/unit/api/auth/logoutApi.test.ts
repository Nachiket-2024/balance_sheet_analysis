import { describe, it, expect, beforeEach } from 'vitest';
import MockAdapter from 'axios-mock-adapter';
import api from '@/api/axiosInstance';
import { logoutApi, logoutAllApi } from '@/api/auth_api';

const mock = new MockAdapter(api);

describe('logoutApi', () => {
  beforeEach(() => {
    mock.reset();
  });

  it('should send POST request to /auth/logout with no body (refresh_token comes from cookies)', async () => {
    const mockResponse = { message: 'Logged out successfully' };
    mock.onPost('/auth/logout').reply((config) => {
      // No JSON body should be sent : the backend reads refresh_token
      // straight from the request's cookies, never from the payload.
      expect(config.data).toBeUndefined();
      return [200, mockResponse];
    });

    const response = await logoutApi();
    expect(response.status).toBe(200);
    expect(response.data).toEqual(mockResponse);
  });

  it('should reject when there is no refresh token cookie to revoke', async () => {
    mock.onPost('/auth/logout').reply(400, { error: 'No refresh token cookie found' });

    await expect(logoutApi()).rejects.toMatchObject({
      response: { status: 400, data: { error: 'No refresh token cookie found' } },
    });
  });
});

describe('logoutAllApi', () => {
  beforeEach(() => {
    mock.reset();
  });

  it('should send POST request to /auth/logout/all', async () => {
    const mockResponse = { message: 'Logged out from 3 devices' };
    mock.onPost('/auth/logout/all').reply(200, mockResponse);

    const response = await logoutAllApi();
    expect(response.status).toBe(200);
    expect(response.data).toEqual(mockResponse);
  });

  it('should reject when the refresh token is invalid', async () => {
    mock.onPost('/auth/logout/all').reply(400, { error: 'Invalid refresh token' });

    await expect(logoutAllApi()).rejects.toMatchObject({
      response: { status: 400, data: { error: 'Invalid refresh token' } },
    });
  });

  it('should hit a distinct endpoint from single-device logout', async () => {
    // Regression guard: these must never collapse onto the same route :
    // logoutApi only ends one session, logoutAllApi ends every session.
    mock.onPost('/auth/logout').reply(200, { message: 'Logged out successfully' });
    mock.onPost('/auth/logout/all').reply(200, { message: 'Logged out from 1 devices' });

    await logoutApi();
    await logoutAllApi();

    const postUrls = mock.history.post.map((req) => req.url);
    expect(postUrls).toEqual(['/auth/logout', '/auth/logout/all']);
  });
});
