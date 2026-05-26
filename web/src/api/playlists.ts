import { apiRequest } from '@/api/client';
import type {
  AddTracksRequest,
  CreatePlaylistRequest,
  PlaylistDetail,
  PlaylistSummary,
} from '@/types';

export async function getPlaylists(): Promise<PlaylistSummary[]> {
  const data = await apiRequest<PlaylistSummary[] | { items: PlaylistSummary[] }>('/api/v1/playlists');
  return Array.isArray(data) ? data : data.items;
}

export async function createPlaylist(payload: CreatePlaylistRequest): Promise<PlaylistSummary> {
  return apiRequest<PlaylistSummary>('/api/v1/playlists', {
    method: 'POST',
    body: payload,
  });
}

export async function getPlaylist(id: string): Promise<PlaylistDetail> {
  return apiRequest<PlaylistDetail>(`/api/v1/playlists/${id}`);
}

export async function addTracksToPlaylist(id: string, payload: AddTracksRequest): Promise<void> {
  await apiRequest(`/api/v1/playlists/${id}/tracks`, {
    method: 'POST',
    body: payload,
  });
}

export async function removeTrackFromPlaylist(playlistId: string, trackId: string): Promise<void> {
  await apiRequest(`/api/v1/playlists/${playlistId}/tracks/${trackId}`, {
    method: 'DELETE',
  });
}
