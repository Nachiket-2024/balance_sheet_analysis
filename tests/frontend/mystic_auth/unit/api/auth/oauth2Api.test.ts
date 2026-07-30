import { describe, it, expect, beforeEach } from 'vitest';
import MockAdapter from 'axios-mock-adapter';
import api from '@/api/axiosInstance';
import { oauth2LoginGoogleApi, oauth2CallbackGoogleApi } from '@/api/auth_api';

const mock = new MockAdapter(api);

// The real Google login flow uses a full-page redirect (OAuth2LoginButton.tsx),
// not these functions : a redirect can't be done via XHR/fetch. They're
// tested here as plain API-layer functions in case a future flow calls
// them programmatically.
describe('oauth2LoginGoogleApi', () => {
  beforeEach(() => {
    mock.reset();
  });

  it('should send GET request to /auth/oauth2/login/google', async () => {
    mock.onGet('/auth/oauth2/login/google').reply(200, {});

    const response = await oauth2LoginGoogleApi();
    expect(response.status).toBe(200);
  });
});

describe('oauth2CallbackGoogleApi', () => {
  beforeEach(() => {
    mock.reset();
  });

  it('should send GET request to /auth/oauth2/callback/google with the code as a query param', async () => {
    mock.onGet('/auth/oauth2/callback/google').reply((config) => {
      expect(config.params).toEqual({ code: 'google-auth-code-abc' });
      return [200, { message: 'Login successful' }];
    });

    await oauth2CallbackGoogleApi('google-auth-code-abc');
  });

  it('should reject when Google reports an unverified email', async () => {
    mock.onGet('/auth/oauth2/callback/google').reply(400, { error: 'Unverified Google email' });

    await expect(oauth2CallbackGoogleApi('bad-code')).rejects.toMatchObject({
      response: { status: 400 },
    });
  });
});
