import { apiRequest } from '@/api/client';
import type { LoginRequest, TokenResponse, User } from '@/types';

export async function login(credentials: LoginRequest): Promise<TokenResponse> {
  return apiRequest<TokenResponse>('/api/v1/auth/login', {
    method: 'POST',
    body: credentials,
    auth: false,
  });
}

export async function getMe(): Promise<User> {
  return apiRequest<User>('/api/v1/auth/me');
}

export async function logout(): Promise<void> {
  const refreshToken = localStorage.getItem('local_music_refresh_token');
  if (refreshToken) {
    try {
      await apiRequest('/api/v1/auth/logout', {
        method: 'POST',
        body: { refresh_token: refreshToken },
      });
    } catch {
      // ignore logout errors
    }
  }
}
