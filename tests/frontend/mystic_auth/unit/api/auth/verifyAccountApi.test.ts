import { describe, it, expect, beforeEach } from 'vitest';
import MockAdapter from 'axios-mock-adapter';
import api from '@/api/axiosInstance';
import { verificationEmailRequestApi, verifyAccountApi } from '@/api/auth_api';

const mock = new MockAdapter(api);

describe('verifyAccountApi', () => {
  beforeEach(() => {
    mock.reset();
  });

  // Regression guard: the verification token must travel in the POST body,
  // not as a GET query parameter : a token in a URL ends up in browser
  // history, server access logs, and Referer headers.
  it('should send POST request to /auth/verify-account with the token in the body', async () => {
    const mockResponse = { message: 'Account verified successfully for test@example.com.' };

    mock.onPost('/auth/verify-account', { token: 'verify-token-abc' }).reply(200, mockResponse);

    const response = await verifyAccountApi('verify-token-abc', 'test@example.com');
    expect(response.status).toBe(200);
    expect(response.data).toEqual(mockResponse);
  });

  it('should not send the token as a query parameter', async () => {
    mock.onGet('/auth/verify-account').reply(200, {});
    mock.onPost('/auth/verify-account').reply(200, { message: 'ok' });

    await verifyAccountApi('verify-token-abc', 'test@example.com');

    const getRequests = mock.history.get.filter((req) => req.url === '/auth/verify-account');
    expect(getRequests).toHaveLength(0);
  });

  it('should handle verification error', async () => {
    mock.onPost('/auth/verify-account').reply(400, { error: 'Invalid or expired verification token' });

    await expect(verifyAccountApi('bad-token', 'test@example.com')).rejects.toThrow();
  });

  it('should request a new verification link by email', async () => {
    const mockResponse = {
      message: "If this account exists and still needs verification, we've sent a new verification link.",
    };

    mock.onPost('/auth/verify-account/request', { email: 'test@example.com' }).reply(200, mockResponse);

    const response = await verificationEmailRequestApi({ email: 'test@example.com' });
    expect(response.status).toBe(200);
    expect(response.data).toEqual(mockResponse);
  });
});
