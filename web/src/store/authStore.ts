import { create } from 'zustand';
import { getMe, login as loginApi, logout as logoutApi } from '@/api/auth';
import { clearTokens, getAccessToken, setTokens } from '@/lib/storage';
import type { LoginRequest, User } from '@/types';

interface AuthState {
  user: User | null;
  isAuthenticated: boolean;
  isLoading: boolean;
  error: string | null;
  initialize: () => Promise<void>;
  login: (credentials: LoginRequest) => Promise<void>;
  logout: () => Promise<void>;
  clearError: () => void;
}

export const useAuthStore = create<AuthState>((set) => ({
  user: null,
  isAuthenticated: Boolean(getAccessToken()),
  isLoading: Boolean(getAccessToken()),
  error: null,

  initialize: async () => {
    const token = getAccessToken();
    if (!token) {
      set({ user: null, isAuthenticated: false, isLoading: false });
      return;
    }

    set({ isLoading: true });
    try {
      const user = await getMe();
      set({ user, isAuthenticated: true, isLoading: false, error: null });
    } catch {
      clearTokens();
      set({ user: null, isAuthenticated: false, isLoading: false });
    }
  },

  login: async (credentials) => {
    set({ isLoading: true, error: null });
    try {
      const tokens = await loginApi(credentials);
      setTokens(tokens.access_token, tokens.refresh_token);
      const user = await getMe();
      set({ user, isAuthenticated: true, isLoading: false, error: null });
    } catch (err) {
      clearTokens();
      const message = err instanceof Error ? err.message : 'Login failed';
      set({ user: null, isAuthenticated: false, isLoading: false, error: message });
      throw err;
    }
  },

  logout: async () => {
    await logoutApi();
    clearTokens();
    set({ user: null, isAuthenticated: false, error: null });
  },

  clearError: () => set({ error: null }),
}));
