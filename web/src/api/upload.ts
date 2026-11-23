import { apiFormRequest, apiRequest } from '@/api/client';

export interface UploadArtist {
  name: string;
  role: 'main' | 'feat' | 'remixer';
}

export interface UploadMeta {
  title: string;
  artists: UploadArtist[];
  album?: string | null;
  year?: number | null;
  genres: string[];
  language?: string | null;
  instrumental: boolean;
  has_lyrics: boolean;
}

export interface ParsedUploadMeta extends UploadMeta {
  isrc?: string | null;
  duration_seconds?: number | null;
  has_cover?: boolean;
}

export interface UploadCreated {
  upload_id: string;
  parsed_meta: ParsedUploadMeta;
  verification_pending: boolean;
}

export interface CandidateSource {
  kind: string;
  source_id: string;
  url: string;
  match: number;
  duration_delta: number | null;
  title: string;
  channel?: string | null;
  thumbnail?: string | null;
}

export interface VerificationResult {
  trust_level: 'high' | 'medium' | 'low' | 'none';
  score: number;
  suggestions: {
    title?: string | null;
    artist?: string | null;
    album?: string | null;
    year?: number | null;
    mbid?: string | null;
    genres?: string[];
  };
  sources_verification: string[];
  candidate_sources: CandidateSource[];
  primary_source_index: number | null;
  album_conflict: boolean;
}

export interface ConfirmResult {
  track_id: string;
  already_exists: boolean;
  rejected_source_ids: string[];
}

export function sourceKey(source: CandidateSource): string {
  return `${source.kind}:${source.source_id}`;
}

export async function uploadTrack(
  file: File,
  meta?: UploadMeta | null,
  cover?: File | null,
): Promise<UploadCreated> {
  const form = new FormData();
  form.append('file', file);
  if (meta) {
    form.append('meta', JSON.stringify(meta));
  }
  if (cover) {
    form.append('cover', cover);
  }
  return apiFormRequest<UploadCreated>('/api/v1/tracks/upload', form);
}

export async function verifyUpload(uploadId: string, meta: UploadMeta): Promise<VerificationResult> {
  return apiRequest<VerificationResult>(
    `/api/v1/tracks/upload/${uploadId}/verify`,
    {},
    { meta: JSON.stringify(meta) },
  );
}

export async function confirmUpload(
  uploadId: string,
  body: {
    meta: UploadMeta;
    accept_suggestions: boolean;
    force: boolean;
    selected_source_ids: string[];
    primary_source_id: string | null;
  },
): Promise<ConfirmResult> {
  return apiRequest<ConfirmResult>(`/api/v1/tracks/upload/${uploadId}/confirm`, {
    method: 'POST',
    body,
  });
}
