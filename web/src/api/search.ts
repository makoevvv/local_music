import { apiRequest } from '@/api/client';
import type { SearchCandidate, SearchResponse } from '@/types';

export async function searchTracks(query: string, limit = 10): Promise<SearchResponse> {
  return apiRequest<SearchResponse>('/api/v1/search', {
    method: 'POST',
    body: { query, limit },
  });
}

export async function createTrackFromCandidate(candidateId: string): Promise<{
  track_id: string;
  status: string;
}> {
  return apiRequest('/api/v1/tracks/from-candidate', {
    method: 'POST',
    body: { candidate_id: candidateId },
  });
}

export async function getTrackStatus(trackId: string): Promise<{
  track_id: string;
  status: string;
  error?: string;
  existing_track_id?: string;
}> {
  return apiRequest(`/api/v1/tracks/${trackId}/status`);
}

export type { SearchCandidate };
