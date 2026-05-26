import { useState } from 'react';
import { Link, useParams } from 'react-router-dom';
import { useQuery } from '@tanstack/react-query';
import { getTrack } from '@/api/tracks';
import { AddToPlaylistModal } from '@/components/AddToPlaylistModal';
import { LikeButton } from '@/components/LikeButton';
import { formatArtists, formatDuration } from '@/lib/utils';
import { usePlayerStore } from '@/store/playerStore';

export function TrackPage() {
  const { id = '' } = useParams();
  const [showPlaylistModal, setShowPlaylistModal] = useState(false);

  const playTrack = usePlayerStore((state) => state.playTrack);
  const addToQueue = usePlayerStore((state) => state.addToQueue);
  const currentTrack = usePlayerStore((state) => state.currentTrack);

  const { data: track, isLoading, isError, error } = useQuery({
    queryKey: ['track', id],
    queryFn: () => getTrack(id),
    enabled: Boolean(id),
  });

  if (isLoading) {
    return <div className="text-sm text-zinc-400">Loading track…</div>;
  }

  if (isError || !track) {
    return (
      <div className="space-y-4">
        <Link to="/catalog" className="text-sm text-accent hover:text-accent-hover">
          ← Back to catalog
        </Link>
        <div className="card p-6 text-sm text-red-400">
          {error instanceof Error ? error.message : 'Track not found'}
        </div>
      </div>
    );
  }

  const isPlaying = currentTrack?.id === track.id;

  return (
    <div className="space-y-6">
      <Link to="/catalog" className="inline-block text-sm text-accent hover:text-accent-hover">
        ← Back to catalog
      </Link>

      <div className="card p-6 sm:p-8">
        <div className="flex flex-col gap-6 sm:flex-row sm:items-start sm:justify-between">
          <div className="space-y-3">
            <h1 className="text-3xl font-semibold text-white">{track.title}</h1>
            <p className="text-lg text-zinc-400">{formatArtists(track.artists)}</p>
            {track.album && (
              <p className="text-sm text-zinc-500">
                {track.album.title}
                {track.album.release_year ? ` · ${track.album.release_year}` : ''}
              </p>
            )}
            <div className="flex flex-wrap gap-2 pt-2">
              {track.genres.map((genre) => (
                <span
                  key={genre.id}
                  className="rounded-full bg-surface-overlay px-3 py-1 text-xs text-zinc-300"
                >
                  {genre.name}
                </span>
              ))}
              {track.languages.map((language) => (
                <span
                  key={language.id}
                  className="rounded-full border border-surface-border px-3 py-1 text-xs text-zinc-400"
                >
                  {language.name}
                </span>
              ))}
            </div>
          </div>

          <div className="flex items-center gap-2">
            <button
              type="button"
              className="btn-primary"
              onClick={() => playTrack(track)}
            >
              {isPlaying ? 'Playing' : 'Play'}
            </button>
            <button type="button" className="btn-ghost" onClick={() => addToQueue(track)}>
              Add to queue
            </button>
            <LikeButton track={track} />
            <button type="button" className="btn-ghost" onClick={() => setShowPlaylistModal(true)}>
              Add to playlist
            </button>
          </div>
        </div>

        <dl className="mt-8 grid gap-4 border-t border-surface-border pt-6 sm:grid-cols-2 lg:grid-cols-4">
          <div>
            <dt className="text-xs uppercase tracking-wide text-zinc-500">Duration</dt>
            <dd className="mt-1 text-sm text-white">{formatDuration(track.duration_seconds)}</dd>
          </div>
          <div>
            <dt className="text-xs uppercase tracking-wide text-zinc-500">Plays</dt>
            <dd className="mt-1 text-sm text-white">{track.play_count}</dd>
          </div>
          <div>
            <dt className="text-xs uppercase tracking-wide text-zinc-500">Format</dt>
            <dd className="mt-1 text-sm text-white">{track.file_format ?? '—'}</dd>
          </div>
          <div>
            <dt className="text-xs uppercase tracking-wide text-zinc-500">Status</dt>
            <dd className="mt-1 text-sm capitalize text-white">{track.status}</dd>
          </div>
          {track.bpm != null && (
            <div>
              <dt className="text-xs uppercase tracking-wide text-zinc-500">BPM</dt>
              <dd className="mt-1 text-sm text-white">{Math.round(track.bpm)}</dd>
            </div>
          )}
          {track.energy != null && (
            <div>
              <dt className="text-xs uppercase tracking-wide text-zinc-500">Energy</dt>
              <dd className="mt-1 text-sm text-white">{track.energy.toFixed(2)}</dd>
            </div>
          )}
        </dl>
      </div>

      {showPlaylistModal && (
        <AddToPlaylistModal track={track} onClose={() => setShowPlaylistModal(false)} />
      )}
    </div>
  );
}
