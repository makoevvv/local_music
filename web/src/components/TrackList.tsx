import { TrackRow } from '@/components/TrackRow';
import type { TrackSummary } from '@/types';

interface TrackListProps {
  tracks: TrackSummary[];
  showIndex?: boolean;
  onPlayTrack?: (track: TrackSummary) => void;
  onRemoveTrack?: (trackId: string) => void;
  emptyMessage?: string;
}

export function TrackList({
  tracks,
  showIndex = false,
  onPlayTrack,
  onRemoveTrack,
  emptyMessage = 'No tracks found.',
}: TrackListProps) {
  if (tracks.length === 0) {
    return (
      <div className="card flex min-h-40 items-center justify-center p-8 text-sm text-zinc-400">
        {emptyMessage}
      </div>
    );
  }

  return (
    <div className="card divide-y divide-surface-border overflow-hidden">
      {tracks.map((track, index) => (
        <TrackRow
          key={track.id}
          track={track}
          index={index}
          showIndex={showIndex}
          onPlay={onPlayTrack}
          onRemove={onRemoveTrack}
        />
      ))}
    </div>
  );
}
