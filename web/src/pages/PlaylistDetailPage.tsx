import { Link, useParams } from 'react-router-dom';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { getPlaylist, removeTrackFromPlaylist } from '@/api/playlists';
import { TrackList } from '@/components/TrackList';
import { usePlayerStore } from '@/store/playerStore';
import type { TrackSummary } from '@/types';

export function PlaylistDetailPage() {
  const { id = '' } = useParams();
  const queryClient = useQueryClient();
  const playQueue = usePlayerStore((state) => state.playQueue);

  const { data: playlist, isLoading, isError, error } = useQuery({
    queryKey: ['playlist', id],
    queryFn: () => getPlaylist(id),
    enabled: Boolean(id),
  });

  const removeMutation = useMutation({
    mutationFn: (trackId: string) => removeTrackFromPlaylist(id, trackId),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ['playlist', id] });
      void queryClient.invalidateQueries({ queryKey: ['playlists'] });
    },
  });

  if (isLoading) {
    return <div className="text-sm text-zinc-400">Loading playlist…</div>;
  }

  if (isError || !playlist) {
    return (
      <div className="space-y-4">
        <Link to="/playlists" className="text-sm text-accent hover:text-accent-hover">
          ← Back to playlists
        </Link>
        <div className="card p-6 text-sm text-red-400">
          {error instanceof Error ? error.message : 'Playlist not found'}
        </div>
      </div>
    );
  }

  const tracks: TrackSummary[] = playlist.tracks.map((item) => item.track);

  const handlePlayTrack = (track: TrackSummary) => {
    const startIndex = tracks.findIndex((item) => item.id === track.id);
    playQueue(tracks, startIndex >= 0 ? startIndex : 0);
  };

  return (
    <div className="space-y-6">
      <Link to="/playlists" className="inline-block text-sm text-accent hover:text-accent-hover">
        ← Back to playlists
      </Link>

      <div className="flex flex-col gap-4 sm:flex-row sm:items-end sm:justify-between">
        <div>
          <div className="mb-2 flex items-center gap-2">
            <h1 className="text-2xl font-semibold text-white">{playlist.name}</h1>
            {playlist.is_favourite && (
              <span className="rounded-full bg-accent/20 px-2 py-0.5 text-xs text-accent">
                Favourite
              </span>
            )}
          </div>
          <p className="text-sm text-zinc-400">
            {playlist.track_count} tracks · {playlist.is_public ? 'Public' : 'Private'}
          </p>
        </div>
        {tracks.length > 0 && (
          <button type="button" className="btn-primary" onClick={() => playQueue(tracks)}>
            Play playlist
          </button>
        )}
      </div>

      <TrackList
        tracks={tracks}
        showIndex
        onPlayTrack={handlePlayTrack}
        onRemoveTrack={playlist.is_favourite ? undefined : (trackId) => removeMutation.mutate(trackId)}
        emptyMessage="This playlist is empty."
      />
    </div>
  );
}
