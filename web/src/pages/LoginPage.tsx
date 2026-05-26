import { FormEvent, useState } from 'react';
import { Navigate, useLocation, useNavigate } from 'react-router-dom';
import { useAuthStore } from '@/store/authStore';

export function LoginPage() {
  const navigate = useNavigate();
  const location = useLocation();
  const isAuthenticated = useAuthStore((state) => state.isAuthenticated);
  const isLoading = useAuthStore((state) => state.isLoading);
  const error = useAuthStore((state) => state.error);
  const login = useAuthStore((state) => state.login);
  const clearError = useAuthStore((state) => state.clearError);

  const [loginValue, setLoginValue] = useState('');
  const [password, setPassword] = useState('');

  const from = (location.state as { from?: string } | null)?.from ?? '/catalog';

  if (isAuthenticated && !isLoading) {
    return <Navigate to={from} replace />;
  }

  const handleSubmit = async (event: FormEvent) => {
    event.preventDefault();
    clearError();
    try {
      await login({ login: loginValue, password });
      navigate(from, { replace: true });
    } catch {
      // error stored in auth store
    }
  };

  return (
    <div className="flex min-h-screen items-center justify-center bg-surface px-4">
      <div className="card w-full max-w-md p-8">
        <div className="mb-8 text-center">
          <h1 className="text-2xl font-semibold text-white">Local Music</h1>
          <p className="mt-2 text-sm text-zinc-400">Sign in to browse your library</p>
        </div>

        <form onSubmit={(event) => void handleSubmit(event)} className="space-y-4">
          <div>
            <label htmlFor="login" className="mb-1 block text-sm text-zinc-400">
              Login
            </label>
            <input
              id="login"
              type="text"
              autoComplete="username"
              required
              value={loginValue}
              onChange={(event) => setLoginValue(event.target.value)}
              className="input"
              placeholder="Email or username"
            />
          </div>
          <div>
            <label htmlFor="password" className="mb-1 block text-sm text-zinc-400">
              Password
            </label>
            <input
              id="password"
              type="password"
              autoComplete="current-password"
              required
              value={password}
              onChange={(event) => setPassword(event.target.value)}
              className="input"
            />
          </div>

          {error && <p className="text-sm text-red-400">{error}</p>}

          <button type="submit" disabled={isLoading} className="btn-primary w-full">
            {isLoading ? 'Signing in…' : 'Sign in'}
          </button>
        </form>
      </div>
    </div>
  );
}
