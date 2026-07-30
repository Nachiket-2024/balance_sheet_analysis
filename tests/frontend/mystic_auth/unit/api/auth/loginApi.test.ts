import { describe, it, expect, beforeEach } from 'vitest';
import MockAdapter from 'axios-mock-adapter';
import api from '@/api/axiosInstance';
import { loginApi } from '@/api/auth_api';

const mock = new MockAdapter(api);

describe('loginApi', () => {
  beforeEach(() => {
    mock.reset();
  });

  it('should send POST request to /auth/login with email and password', async () => {
    const payload = { email: 'test@example.com', password: 'Test123!' };
    // Real backend behavior: tokens are set as HttpOnly cookies, never
    // returned in the JSON body : only a generic success message.
    const mockResponse = { message: 'Login successful' };

    mock.onPost('/auth/login', payload).reply(200, mockResponse);

    const response = await loginApi(payload);
    expect(response.status).toBe(200);
    expect(response.data).toEqual(mockResponse);
  });

  it('should reject with the same generic message for wrong password or unknown email', async () => {
    // Backend deliberately returns an identical response for both cases to
    // resist account enumeration : the frontend must not depend on being
    // able to distinguish them.
    mock.onPost('/auth/login').reply(401, { error: 'Invalid credentials or account locked' });

    await expect(loginApi({ email: 'nobody@example.com', password: 'wrong' })).rejects.toMatchObject({
      response: { status: 401, data: { error: 'Invalid credentials or account locked' } },
    });
  });

  it('should propagate a 429 when the account is locked out', async () => {
    mock
      .onPost('/auth/login')
      .reply(429, { error: 'Too many failed login attempts, account temporarily locked' });

    await expect(loginApi({ email: 'test@example.com', password: 'wrong' })).rejects.toMatchObject({
      response: { status: 429 },
    });
  });

  it('should send the request with credentials included (cookie support)', async () => {
    mock.onPost('/auth/login').reply((config) => {
      expect(config.withCredentials).toBe(true);
      return [200, { message: 'Login successful' }];
    });

    await loginApi({ email: 'test@example.com', password: 'Test123!' });
  });
});
