import { usePlayerStore } from '@/store/playerStore';
import { formatArtists, formatDuration } from '@/lib/utils';
import { cn } from '@/lib/utils';

export function QueuePanel() {
  const queue = usePlayerStore((state) => state.queue);
  const currentTrack = usePlayerStore((state) => state.currentTrack);
  const isQueueOpen = usePlayerStore((state) => state.isQueueOpen);
  const setQueueOpen = usePlayerStore((state) => state.setQueueOpen);
  const playTrack = usePlayerStore((state) => state.playTrack);
  const removeFromQueue = usePlayerStore((state) => state.removeFromQueue);
  const clearQueue = usePlayerStore((state) => state.clearQueue);

  if (!isQueueOpen) return null;

  return (
    <div className="fixed bottom-24 right-4 z-40 w-80 overflow-hidden rounded-xl border border-surface-border bg-surface-raised shadow-2xl">
      <div className="flex items-center justify-between border-b border-surface-border px-4 py-3">
        <h3 className="text-sm font-semibold text-white">Queue</h3>
        <div className="flex items-center gap-2">
          {queue.length > 0 && (
            <button type="button" className="text-xs text-zinc-400 hover:text-white" onClick={clearQueue}>
              Clear
            </button>
          )}
          <button type="button" className="btn-icon h-7 w-7" onClick={() => setQueueOpen(false)}>
            ✕
          </button>
        </div>
      </div>
      <ul className="max-h-72 overflow-y-auto">
        {queue.length === 0 ? (
          <li className="px-4 py-6 text-center text-sm text-zinc-500">Queue is empty</li>
        ) : (
          queue.map((track) => (
            <li
              key={track.id}
              className={cn(
                'flex items-center gap-3 border-b border-surface-border px-4 py-3 last:border-b-0',
                currentTrack?.id === track.id && 'bg-accent/10',
              )}
            >
              <button
                type="button"
                className="min-w-0 flex-1 text-left"
                onClick={() => playTrack(track, queue)}
              >
                <p className="truncate text-sm font-medium text-white">{track.title}</p>
                <p className="truncate text-xs text-zinc-500">{formatArtists(track.artists)}</p>
              </button>
              <span className="text-xs tabular-nums text-zinc-500">
                {formatDuration(track.duration_seconds)}
              </span>
              <button
                type="button"
                className="text-zinc-500 hover:text-white"
                aria-label="Remove from queue"
                onClick={() => removeFromQueue(track.id)}
              >
                ✕
              </button>
            </li>
          ))
        )}
      </ul>
    </div>
  );
}
