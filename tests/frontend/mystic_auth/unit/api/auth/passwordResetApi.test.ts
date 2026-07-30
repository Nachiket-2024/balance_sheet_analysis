import { describe, it, expect, beforeEach } from 'vitest';
import MockAdapter from 'axios-mock-adapter';
import api from '@/api/axiosInstance';
import { passwordResetRequestApi, passwordResetConfirmApi } from '@/api/auth_api';

const mock = new MockAdapter(api);

describe('passwordResetRequestApi', () => {
  beforeEach(() => {
    mock.reset();
  });

  it('should send POST request to /auth/password-reset/request with the email', async () => {
    const payload = { email: 'test@example.com' };
    const mockResponse = { message: 'If this email is registered, a reset link has been sent.' };

    mock.onPost('/auth/password-reset/request', payload).reply(200, mockResponse);

    const response = await passwordResetRequestApi(payload);
    expect(response.status).toBe(200);
    expect(response.data).toEqual(mockResponse);
  });

  it('should return the same generic response regardless of whether the email is registered', async () => {
    // Anti-enumeration: the backend always returns 200 with an identical
    // message, whether or not the account exists.
    const mockResponse = { message: 'If this email is registered, a reset link has been sent.' };
    mock.onPost('/auth/password-reset/request').reply(200, mockResponse);

    const known = await passwordResetRequestApi({ email: 'known@example.com' });
    const unknown = await passwordResetRequestApi({ email: 'unknown@example.com' });

    expect(known.data).toEqual(unknown.data);
    expect(known.status).toBe(unknown.status);
  });
});

describe('passwordResetConfirmApi', () => {
  beforeEach(() => {
    mock.reset();
  });

  it('should send POST request to /auth/password-reset/confirm with token and new_password', async () => {
    const payload = { token: 'reset-token-abc', new_password: 'NewStrongPass123!' };
    const mockResponse = { message: 'Password has been reset successfully' };

    mock.onPost('/auth/password-reset/confirm', payload).reply(200, mockResponse);

    const response = await passwordResetConfirmApi(payload);
    expect(response.status).toBe(200);
    expect(response.data).toEqual(mockResponse);
  });

  it('should reject when the token is invalid, expired, or already used', async () => {
    mock.onPost('/auth/password-reset/confirm').reply(400, { error: 'Invalid token or password' });

    await expect(
      passwordResetConfirmApi({ token: 'replayed-token', new_password: 'NewStrongPass123!' })
    ).rejects.toMatchObject({
      response: { status: 400, data: { error: 'Invalid token or password' } },
    });
  });

  it('should not send an email field : the backend derives it from the token', async () => {
    mock.onPost('/auth/password-reset/confirm').reply((config) => {
      const body = JSON.parse(config.data);
      expect(body).toEqual({ token: 'reset-token-abc', new_password: 'NewStrongPass123!' });
      expect(body.email).toBeUndefined();
      return [200, { message: 'Password has been reset successfully' }];
    });

    await passwordResetConfirmApi({ token: 'reset-token-abc', new_password: 'NewStrongPass123!' });
  });
});
