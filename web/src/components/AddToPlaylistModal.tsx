import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { addTracksToPlaylist, getPlaylists } from '@/api/playlists';
import type { TrackSummary } from '@/types';

interface AddToPlaylistModalProps {
  track: TrackSummary;
  onClose: () => void;
}

export function AddToPlaylistModal({ track, onClose }: AddToPlaylistModalProps) {
  const queryClient = useQueryClient();
  const { data: playlists = [], isLoading } = useQuery({
    queryKey: ['playlists'],
    queryFn: getPlaylists,
  });

  const mutation = useMutation({
    mutationFn: (playlistId: string) => addTracksToPlaylist(playlistId, { track_ids: [track.id] }),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ['playlists'] });
      onClose();
    },
  });

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/70 p-4">
      <div className="card w-full max-w-md p-5 shadow-2xl">
        <div className="mb-4 flex items-start justify-between gap-4">
          <div>
            <h2 className="text-lg font-semibold text-white">Add to playlist</h2>
            <p className="mt-1 text-sm text-zinc-400">{track.title}</p>
          </div>
          <button type="button" className="btn-icon" onClick={onClose} aria-label="Close">
            ✕
          </button>
        </div>

        {isLoading ? (
          <p className="text-sm text-zinc-400">Loading playlists…</p>
        ) : playlists.length === 0 ? (
          <p className="text-sm text-zinc-400">No playlists yet. Create one first.</p>
        ) : (
          <ul className="max-h-72 space-y-2 overflow-y-auto">
            {playlists.map((playlist) => (
              <li key={playlist.id}>
                <button
                  type="button"
                  disabled={mutation.isPending}
                  onClick={() => mutation.mutate(playlist.id)}
                  className="flex w-full items-center justify-between rounded-lg border border-surface-border bg-surface px-3 py-3 text-left transition-colors hover:border-accent/40 hover:bg-surface-overlay"
                >
                  <span className="font-medium text-white">{playlist.name}</span>
                  <span className="text-xs text-zinc-500">{playlist.track_count} tracks</span>
                </button>
              </li>
            ))}
          </ul>
        )}

        {mutation.isError && (
          <p className="mt-3 text-sm text-red-400">
            {mutation.error instanceof Error ? mutation.error.message : 'Failed to add track'}
          </p>
        )}
      </div>
    </div>
  );
}
