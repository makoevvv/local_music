import { useState } from 'react';
import { Link } from 'react-router-dom';
import { AddToPlaylistModal } from '@/components/AddToPlaylistModal';
import { LikeButton } from '@/components/LikeButton';
import { formatArtists, formatDuration } from '@/lib/utils';
import { usePlayerStore } from '@/store/playerStore';
import type { TrackSummary } from '@/types';
import { cn } from '@/lib/utils';

interface TrackRowProps {
  track: TrackSummary;
  index?: number;
  showIndex?: boolean;
  onPlay?: (track: TrackSummary) => void;
  onRemove?: (trackId: string) => void;
}

export function TrackRow({ track, index, showIndex = false, onPlay, onRemove }: TrackRowProps) {
  const [showPlaylistModal, setShowPlaylistModal] = useState(false);
  const currentTrack = usePlayerStore((state) => state.currentTrack);
  const playTrack = usePlayerStore((state) => state.playTrack);
  const addToQueue = usePlayerStore((state) => state.addToQueue);
  const isActive = currentTrack?.id === track.id;

  const handlePlay = () => {
    if (onPlay) {
      onPlay(track);
    } else {
      playTrack(track);
    }
  };

  return (
    <>
      <div
        className={cn(
          'group grid grid-cols-[auto_1fr_auto] items-center gap-3 rounded-lg px-3 py-2 transition-colors sm:grid-cols-[auto_1fr_1fr_auto_auto]',
          isActive ? 'bg-accent/10' : 'hover:bg-surface-overlay',
        )}
      >
        <div className="flex w-10 items-center justify-center">
          {showIndex && index != null ? (
            <>
              <span className="text-sm text-zinc-500 group-hover:hidden">{index + 1}</span>
              <button
                type="button"
                className="hidden text-accent group-hover:block"
                onClick={handlePlay}
                aria-label={`Play ${track.title}`}
              >
                ▶
              </button>
            </>
          ) : (
            <button
              type="button"
              className="text-zinc-500 hover:text-accent"
              onClick={handlePlay}
              aria-label={`Play ${track.title}`}
            >
              ▶
            </button>
          )}
        </div>

        <div className="min-w-0">
          <Link
            to={`/tracks/${track.id}`}
            className={cn('block truncate font-medium', isActive ? 'text-accent' : 'text-white')}
          >
            {track.title}
          </Link>
          <p className="truncate text-sm text-zinc-400">{formatArtists(track.artists)}</p>
        </div>

        <p className="hidden truncate text-sm text-zinc-500 sm:block">
          {track.album?.title ?? '—'}
        </p>

        <span className="text-sm tabular-nums text-zinc-500">
          {formatDuration(track.duration_seconds)}
        </span>

        <div className="flex items-center gap-1">
          <LikeButton track={track} size="sm" />
          <button
            type="button"
            className="btn-icon h-8 w-8 text-zinc-400"
            aria-label="Add to playlist"
            onClick={() => setShowPlaylistModal(true)}
          >
            +
          </button>
          <button
            type="button"
            className="btn-icon h-8 w-8 text-zinc-400"
            aria-label="Add to queue"
            onClick={() => addToQueue(track)}
          >
            ☰
          </button>
          {onRemove && (
            <button
              type="button"
              className="btn-icon h-8 w-8 text-red-400"
              aria-label="Remove from playlist"
              onClick={() => onRemove(track.id)}
            >
              ✕
            </button>
          )}
        </div>
      </div>

      {showPlaylistModal && (
        <AddToPlaylistModal track={track} onClose={() => setShowPlaylistModal(false)} />
      )}
    </>
  );
}
