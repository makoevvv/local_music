export type UserRole = 'admin' | 'user';

export type TrackStatus = 'downloading' | 'ready' | 'failed' | 'blocked';

export type LikeSentiment = 'like' | 'dislike';

export type ArtistRole = 'main' | 'feat' | 'remixer';

export interface User {
  id: string;
  email: string;
  username: string;
  role: UserRole;
  is_master: boolean;
  is_active: boolean;
  created_at: string;
}

export interface TokenResponse {
  access_token: string;
  refresh_token: string;
  expires_in: number;
  token_type: string;
}

export interface ArtistRef {
  id: string;
  name: string;
  role?: ArtistRole;
}

export interface AlbumRef {
  id: string;
  title: string;
  release_year?: number | null;
  cover_path?: string | null;
}

export interface Genre {
  id: string;
  name: string;
  slug: string;
}

export interface Language {
  id: string;
  code: string;
  name: string;
}

export interface TrackSummary {
  id: string;
  title: string;
  duration_seconds: number | null;
  status: TrackStatus;
  has_lyrics: boolean;
  play_count: number;
  explicit: boolean;
  artists: ArtistRef[];
  album: AlbumRef | null;
  user_sentiment: LikeSentiment | null;
}

export interface TrackDetail extends TrackSummary {
  genres: Genre[];
  languages: Language[];
  bpm: number | null;
  energy: number | null;
  valence: number | null;
  file_format: string | null;
  source_kind: string | null;
  created_at: string;
}

export interface PaginatedResponse<T> {
  items: T[];
  total?: number;
  page?: number;
  page_size?: number;
  next_cursor?: string | null;
}

export interface PlaylistSummary {
  id: string;
  name: string;
  is_public: boolean;
  is_favourite: boolean;
  track_count: number;
  created_at: string;
  updated_at: string | null;
}

export interface PlaylistTrackItem {
  track_id: string;
  position: number;
  added_at: string;
  track: TrackSummary;
}

export interface PlaylistDetail extends PlaylistSummary {
  tracks: PlaylistTrackItem[];
}

export interface ApiProblem {
  type?: string;
  title?: string;
  status?: number;
  detail?: string;
  trace_id?: string;
}

export interface TracksQueryParams {
  page?: number;
  page_size?: number;
  q?: string;
  genre?: string;
  language?: string;
  has_lyrics?: boolean;
  sort?: string;
}

export interface CreatePlaylistRequest {
  name: string;
  is_public: boolean;
}

export interface AddTracksRequest {
  track_ids: string[];
}

export interface LikeRequest {
  sentiment: LikeSentiment;
}

export interface LoginRequest {
  login: string;
  password: string;
}

export interface SearchCandidate {
  candidate_id: string;
  title: string;
  artist: string;
  duration_seconds: number | null;
  thumbnail_url: string | null;
  source_kind: string;
  source_id: string;
  tier: number;
  restricted: boolean;
}

export interface SearchResponse {
  query: string;
  cached: boolean;
  items: SearchCandidate[];
  warning?: string | null;
}

export interface TrackEventMessage {
  event: string;
  track_id: string;
  status?: string;
  error?: string;
  existing_track_id?: string;
}
