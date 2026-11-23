import { useEffect } from 'react';
import { useQueryClient } from '@tanstack/react-query';
import { getApiBase, getAccessToken } from '@/lib/storage';
import type { TrackEventMessage } from '@/types';

export function useTrackEvents(enabled: boolean) {
  const queryClient = useQueryClient();

  useEffect(() => {
    if (!enabled) {
      return;
    }
    const token = getAccessToken();
    if (!token) {
      return;
    }

    const protocol = window.location.protocol === 'https:' ? 'wss' : 'ws';
    const apiBase = getApiBase();
    const wsBase = apiBase.replace(/^http/, protocol);
    const socket = new WebSocket(`${wsBase}/api/v1/ws/tracks?token=${encodeURIComponent(token)}`);

    socket.onmessage = (event) => {
      try {
        const message = JSON.parse(event.data as string) as TrackEventMessage;
        if (message.event === 'track.ready' || message.event === 'track.failed') {
          void queryClient.invalidateQueries({ queryKey: ['tracks'] });
          void queryClient.invalidateQueries({ queryKey: ['track', message.track_id] });
        }
      } catch {
        // ignore malformed events
      }
    };

    return () => {
      socket.close();
    };
  }, [enabled, queryClient]);
}
