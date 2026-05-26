import { FormEvent, useState } from 'react';
import { Link } from 'react-router-dom';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { createPlaylist, getPlaylists } from '@/api/playlists';

export function PlaylistsPage() {
  const queryClient = useQueryClient();
  const [name, setName] = useState('');
  const [isPublic, setIsPublic] = useState(false);

  const { data: playlists = [], isLoading, isError, error } = useQuery({
    queryKey: ['playlists'],
    queryFn: getPlaylists,
  });

  const createMutation = useMutation({
    mutationFn: () => createPlaylist({ name: name.trim(), is_public: isPublic }),
    onSuccess: () => {
      setName('');
      setIsPublic(false);
      void queryClient.invalidateQueries({ queryKey: ['playlists'] });
    },
  });

  const handleSubmit = (event: FormEvent) => {
    event.preventDefault();
    if (!name.trim()) return;
    createMutation.mutate();
  };

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-semibold text-white">Playlists</h1>
        <p className="mt-1 text-sm text-zinc-400">Your collections and favourites</p>
      </div>

      <form onSubmit={handleSubmit} className="card grid gap-3 p-4 sm:grid-cols-[1fr_auto_auto]">
        <input
          type="text"
          placeholder="New playlist name"
          value={name}
          onChange={(event) => setName(event.target.value)}
          className="input"
        />
        <label className="flex items-center gap-2 text-sm text-zinc-400">
          <input
            type="checkbox"
            checked={isPublic}
            onChange={(event) => setIsPublic(event.target.checked)}
            className="rounded border-surface-border bg-surface"
          />
          Public
        </label>
        <button type="submit" disabled={createMutation.isPending || !name.trim()} className="btn-primary">
          Create
        </button>
      </form>

      {createMutation.isError && (
        <p className="text-sm text-red-400">
          {createMutation.error instanceof Error
            ? createMutation.error.message
            : 'Failed to create playlist'}
        </p>
      )}

      {isLoading ? (
        <div className="text-sm text-zinc-400">Loading playlists…</div>
      ) : isError ? (
        <div className="card p-6 text-sm text-red-400">
          {error instanceof Error ? error.message : 'Failed to load playlists'}
        </div>
      ) : playlists.length === 0 ? (
        <div className="card p-8 text-center text-sm text-zinc-400">No playlists yet.</div>
      ) : (
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {playlists.map((playlist) => (
            <Link
              key={playlist.id}
              to={`/playlists/${playlist.id}`}
              className="card block p-5 transition-colors hover:border-accent/40 hover:bg-surface-overlay"
            >
              <div className="mb-3 flex items-start justify-between gap-3">
                <h2 className="font-semibold text-white">{playlist.name}</h2>
                {playlist.is_favourite && (
                  <span className="rounded-full bg-accent/20 px-2 py-0.5 text-xs text-accent">
                    Favourite
                  </span>
                )}
              </div>
              <p className="text-sm text-zinc-400">
                {playlist.track_count} tracks
                {playlist.is_public ? ' · Public' : ' · Private'}
              </p>
            </Link>
          ))}
        </div>
      )}
    </div>
  );
}
