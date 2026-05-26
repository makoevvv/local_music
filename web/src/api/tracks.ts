import { apiRequest } from '@/api/client';
import type {
  LikeRequest,
  PaginatedResponse,
  TrackDetail,
  TrackSummary,
  TracksQueryParams,
} from '@/types';

export async function getTracks(params: TracksQueryParams): Promise<PaginatedResponse<TrackSummary>> {
  return apiRequest<PaginatedResponse<TrackSummary>>(
    '/api/v1/tracks',
    { method: 'GET' },
    params as Record<string, string | number | boolean | undefined>,
  );
}

export async function getTrack(id: string): Promise<TrackDetail> {
  return apiRequest<TrackDetail>(`/api/v1/tracks/${id}`);
}

export async function likeTrack(id: string, sentiment: LikeRequest['sentiment']): Promise<void> {
  await apiRequest(`/api/v1/tracks/${id}/like`, {
    method: 'PUT',
    body: { sentiment },
  });
}

export async function unlikeTrack(id: string): Promise<void> {
  await apiRequest(`/api/v1/tracks/${id}/like`, { method: 'DELETE' });
}

export async function logPlay(id: string): Promise<{ play_id: number }> {
  return apiRequest<{ play_id: number }>(`/api/v1/tracks/${id}/play`, { method: 'POST' });
}
