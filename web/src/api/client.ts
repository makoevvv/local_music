import type { ApiProblem } from '@/types';
import {
  clearTokens,
  getAccessToken,
  getApiBase,
  getRefreshToken,
  setTokens,
} from '@/lib/storage';

export class ApiError extends Error {
  status: number;
  problem?: ApiProblem;

  constructor(message: string, status: number, problem?: ApiProblem) {
    super(message);
    this.name = 'ApiError';
    this.status = status;
    this.problem = problem;
  }
}

type RequestOptions = Omit<RequestInit, 'body'> & {
  body?: unknown;
  auth?: boolean;
};

let refreshPromise: Promise<boolean> | null = null;

async function refreshAccessToken(): Promise<boolean> {
  const refreshToken = getRefreshToken();
  if (!refreshToken) {
    return false;
  }

  const response = await fetch(`${getApiBase()}/api/v1/auth/refresh`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ refresh_token: refreshToken }),
  });

  if (!response.ok) {
    clearTokens();
    return false;
  }

  const data = (await response.json()) as {
    access_token: string;
    refresh_token: string;
  };
  setTokens(data.access_token, data.refresh_token);
  return true;
}

async function ensureRefreshed(): Promise<boolean> {
  if (!refreshPromise) {
    refreshPromise = refreshAccessToken().finally(() => {
      refreshPromise = null;
    });
  }
  return refreshPromise;
}

function buildUrl(path: string, params?: Record<string, string | number | boolean | undefined>): string {
  const url = new URL(`${getApiBase()}${path}`);
  if (params) {
    for (const [key, value] of Object.entries(params)) {
      if (value !== undefined && value !== '') {
        url.searchParams.set(key, String(value));
      }
    }
  }
  return url.toString();
}

export async function apiRequest<T>(
  path: string,
  options: RequestOptions = {},
  params?: Record<string, string | number | boolean | undefined>,
): Promise<T> {
  const { body, auth = true, headers, ...rest } = options;
  const requestHeaders = new Headers(headers);

  if (body !== undefined) {
    requestHeaders.set('Content-Type', 'application/json');
  }

  if (auth) {
    const token = getAccessToken();
    if (token) {
      requestHeaders.set('Authorization', `Bearer ${token}`);
    }
  }

  const doFetch = () =>
    fetch(buildUrl(path, params), {
      ...rest,
      headers: requestHeaders,
      body: body !== undefined ? JSON.stringify(body) : undefined,
    });

  let response = await doFetch();

  if (response.status === 401 && auth) {
    const refreshed = await ensureRefreshed();
    if (refreshed) {
      const token = getAccessToken();
      if (token) {
        requestHeaders.set('Authorization', `Bearer ${token}`);
      }
      response = await doFetch();
    }
  }

  if (response.status === 204) {
    return undefined as T;
  }

  const contentType = response.headers.get('content-type') ?? '';
  const isJson = contentType.includes('application/json') || contentType.includes('application/problem+json');

  if (!response.ok) {
    let problem: ApiProblem | undefined;
    if (isJson) {
      problem = (await response.json()) as ApiProblem;
    }
    throw new ApiError(
      problem?.detail ?? problem?.title ?? `Request failed (${response.status})`,
      response.status,
      problem,
    );
  }

  if (!isJson) {
    return response as unknown as T;
  }

  return (await response.json()) as T;
}

export async function fetchStreamBlob(trackId: string): Promise<Blob> {
  const token = getAccessToken();
  const headers: HeadersInit = {};
  if (token) {
    headers.Authorization = `Bearer ${token}`;
  }

  let response = await fetch(`${getApiBase()}/api/v1/tracks/${trackId}/stream`, { headers });

  if (response.status === 401) {
    const refreshed = await ensureRefreshed();
    if (refreshed) {
      const newToken = getAccessToken();
      if (newToken) {
        headers.Authorization = `Bearer ${newToken}`;
      }
      response = await fetch(`${getApiBase()}/api/v1/tracks/${trackId}/stream`, { headers });
    }
  }

  if (!response.ok) {
    throw new ApiError(`Failed to stream track (${response.status})`, response.status);
  }

  return response.blob();
}
