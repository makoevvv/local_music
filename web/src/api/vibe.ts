import { apiRequest } from '@/api/client';
import type { TrackSummary } from '@/types';

export interface VibeSettings {
  mood: string;
  genres: string[];
  languages: string[];
  mode: string;
  explicit_allowed: boolean;
  no_lyrics: boolean;
}

export interface VibeTrack {
  id: string;
  title: string;
  duration_seconds: number | null;
  status: TrackSummary['status'];
  play_count: number;
  has_lyrics: boolean;
  artists: TrackSummary['artists'];
  album: TrackSummary['album'];
  unverified?: boolean;
  user_sentiment: TrackSummary['user_sentiment'];
}

export interface VibeQueue {
  session_id: string;
  queue: VibeTrack[];
}

export interface VibePreset {
  id: string;
  name: string;
  settings: VibeSettings;
}

export function toTrackSummary(track: VibeTrack): TrackSummary {
  return {
    id: track.id,
    title: track.title,
    duration_seconds: track.duration_seconds,
    status: track.status,
    has_lyrics: track.has_lyrics,
    play_count: track.play_count,
    explicit: false,
    unverified: track.unverified,
    artists: track.artists,
    album: track.album,
    user_sentiment: track.user_sentiment,
  };
}

export function startVibe(settings: VibeSettings): Promise<VibeQueue> {
  return apiRequest<VibeQueue>('/api/v1/vibe/session', {
    method: 'POST',
    body: settings,
  });
}

export function nextVibe(sessionId: string): Promise<VibeQueue> {
  return apiRequest<VibeQueue>(`/api/v1/vibe/${sessionId}/next`, { method: 'POST' });
}

export function sendVibeFeedback(
  sessionId: string,
  trackId: string,
  action: 'like' | 'dislike' | 'skip' | 'played',
): Promise<void> {
  return apiRequest<void>(`/api/v1/vibe/${sessionId}/feedback`, {
    method: 'POST',
    body: { track_id: trackId, action },
  });
}

export function listVibePresets(): Promise<VibePreset[]> {
  return apiRequest<VibePreset[]>('/api/v1/vibe/presets');
}

export function saveVibePreset(name: string, settings: VibeSettings): Promise<VibePreset> {
  return apiRequest<VibePreset>('/api/v1/vibe/presets', {
    method: 'POST',
    body: { name, ...settings },
  });
}
