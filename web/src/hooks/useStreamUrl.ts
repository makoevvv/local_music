import { useEffect, useRef, useState } from 'react';
import { fetchStreamBlob } from '@/api/client';

const blobCache = new Map<string, string>();

export function useStreamUrl(trackId: string | null): {
  streamUrl: string | null;
  isLoading: boolean;
  error: string | null;
} {
  const [streamUrl, setStreamUrl] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const objectUrlRef = useRef<string | null>(null);

  useEffect(() => {
    if (!trackId) {
      setStreamUrl(null);
      setError(null);
      setIsLoading(false);
      return;
    }

    let cancelled = false;

    async function loadStream() {
      setIsLoading(true);
      setError(null);

      try {
        const cached = blobCache.get(trackId!);
        if (cached) {
          if (!cancelled) {
            setStreamUrl(cached);
            setIsLoading(false);
          }
          return;
        }

        const blob = await fetchStreamBlob(trackId!);
        const url = URL.createObjectURL(blob);
        blobCache.set(trackId!, url);

        if (!cancelled) {
          if (objectUrlRef.current && !blobCache.has(trackId!)) {
            URL.revokeObjectURL(objectUrlRef.current);
          }
          objectUrlRef.current = url;
          setStreamUrl(url);
        }
      } catch (err) {
        if (!cancelled) {
          setStreamUrl(null);
          setError(err instanceof Error ? err.message : 'Failed to load stream');
        }
      } finally {
        if (!cancelled) {
          setIsLoading(false);
        }
      }
    }

    void loadStream();

    return () => {
      cancelled = true;
    };
  }, [trackId]);

  return { streamUrl, isLoading, error };
}

export function revokeStreamCache(): void {
  for (const url of blobCache.values()) {
    URL.revokeObjectURL(url);
  }
  blobCache.clear();
}
