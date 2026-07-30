import { describe, it, expect, beforeEach } from 'vitest';
import MockAdapter from 'axios-mock-adapter';
import api from '@/api/axiosInstance';
import { signupApi } from '@/api/auth_api';

const mock = new MockAdapter(api);

describe('signupApi', () => {
  beforeEach(() => {
    mock.reset();
  });

  it('should send POST request to /auth/signup with user data', async () => {
    const payload = {
      name: 'Test User',
      email: 'test@example.com',
      password: 'Test123!',
    };
    const mockResponse = { message: 'Signup successful', user_id: '123' };
    
    mock.onPost('/auth/signup', payload).reply(201, mockResponse);
    
    const response = await signupApi(payload);
    expect(response.status).toBe(201);
    expect(response.data).toEqual(mockResponse);
  });

  it('should handle signup error', async () => {
    const payload = {
      name: 'Test User',
      email: 'existing@example.com',
      password: 'Test123!',
    };
    
    mock.onPost('/auth/signup').reply(400, { error: 'Email already exists' });
    
    await expect(signupApi(payload)).rejects.toThrow();
  });
});