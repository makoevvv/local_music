import { FormEvent, useState } from 'react';
import { useMutation } from '@tanstack/react-query';
import { Link } from 'react-router-dom';
import { createTrackFromCandidate, getTrackStatus, searchTracks } from '@/api/search';
import { formatDuration } from '@/lib/utils';
import type { SearchCandidate } from '@/types';

type PendingDownload = {
  trackId: string;
  title: string;
  status: string;
  error?: string;
  existingTrackId?: string;
};

export function SearchPage() {
  const [query, setQuery] = useState('');
  const [results, setResults] = useState<SearchCandidate[]>([]);
  const [cached, setCached] = useState(false);
  const [pending, setPending] = useState<PendingDownload[]>([]);

  const [warning, setWarning] = useState<string | null>(null);

  const searchMutation = useMutation({
    mutationFn: (value: string) => searchTracks(value, 10),
    onSuccess: (data) => {
      setResults(data.items);
      setCached(data.cached);
      setWarning(data.warning ?? null);
    },
    onError: () => {
      setWarning(null);
    },
  });

  const downloadMutation = useMutation({
    mutationFn: (candidateId: string) => createTrackFromCandidate(candidateId),
    onSuccess: (data, candidateId) => {
      const item = results.find((candidate) => candidate.candidate_id === candidateId);
      setPending((current) => [
        ...current,
        {
          trackId: data.track_id,
          title: item?.title ?? 'Track',
          status: data.status,
        },
      ]);
      void pollStatus(data.track_id);
    },
  });

  const pollStatus = async (trackId: string) => {
    const maxAttempts = 120;
    for (let attempt = 0; attempt < maxAttempts; attempt += 1) {
      await new Promise((resolve) => setTimeout(resolve, 2000));
      const status = await getTrackStatus(trackId);
      setPending((current) =>
        current.map((item) =>
          item.trackId === trackId
            ? {
                ...item,
                status: status.status,
                error: status.error,
                existingTrackId: status.existing_track_id,
              }
            : item,
        ),
      );
      if (status.status === 'ready' || status.status === 'failed') {
        return;
      }
    }
  };

  const handleSubmit = (event: FormEvent) => {
    event.preventDefault();
    const trimmed = query.trim();
    if (!trimmed) {
      return;
    }
    searchMutation.mutate(trimmed);
  };

  return (
    <div className="space-y-8">
      <div>
        <h1 className="text-2xl font-semibold text-white">Search</h1>
        <p className="mt-1 text-sm text-zinc-400">
          Find tracks on YouTube and SoundCloud, then add them to your library.
        </p>
      </div>

      <form onSubmit={handleSubmit} className="flex flex-col gap-3 sm:flex-row">
        <input
          className="input flex-1"
          placeholder="Artist or track name"
          value={query}
          onChange={(event) => setQuery(event.target.value)}
        />
        <button
          type="submit"
          className="btn-primary"
          disabled={searchMutation.isPending || !query.trim()}
        >
          {searchMutation.isPending ? 'Searching…' : 'Search'}
        </button>
      </form>

      {searchMutation.isError && (
        <p className="text-sm text-red-400">
          Search timed out or failed. Ensure the backend container can reach YouTube
          (docker compose exec backend curl -I --max-time 10 https://www.youtube.com).
        </p>
      )}

      {warning && !searchMutation.isPending && (
        <p className="text-sm text-amber-400">{warning}</p>
      )}

      {!searchMutation.isPending &&
        !searchMutation.isError &&
        results.length === 0 &&
        searchMutation.isSuccess && (
          <p className="text-sm text-zinc-400">No candidates found for this query.</p>
        )}

      {results.length > 0 && (
        <p className="text-xs uppercase tracking-wide text-zinc-500">
          {cached ? 'Cached results' : 'Fresh results'} · {results.length} candidates
        </p>
      )}

      <ul className="space-y-3">
        {results.map((candidate) => (
          <li
            key={candidate.candidate_id}
            className="flex items-center gap-4 rounded-xl border border-surface-border bg-surface-overlay p-4"
          >
            {candidate.thumbnail_url ? (
              <img
                src={candidate.thumbnail_url}
                alt=""
                className="h-16 w-16 rounded-lg object-cover"
              />
            ) : (
              <div className="flex h-16 w-16 items-center justify-center rounded-lg bg-surface-border text-xs text-zinc-500">
                No art
              </div>
            )}
            <div className="min-w-0 flex-1">
              <p className="truncate font-medium text-white">{candidate.title}</p>
              <p className="truncate text-sm text-zinc-400">{candidate.artist}</p>
              <p className="mt-1 text-xs text-zinc-500">
                {candidate.source_kind}
                {candidate.duration_seconds != null
                  ? ` · ${formatDuration(candidate.duration_seconds)}`
                  : ''}
                {candidate.restricted ? ' · restricted' : ''}
              </p>
            </div>
            <button
              type="button"
              className="btn-primary shrink-0"
              disabled={downloadMutation.isPending}
              onClick={() => downloadMutation.mutate(candidate.candidate_id)}
            >
              Add
            </button>
          </li>
        ))}
      </ul>

      {pending.length > 0 && (
        <section className="space-y-3 rounded-xl border border-surface-border bg-surface-overlay p-4">
          <h2 className="text-sm font-semibold uppercase tracking-wide text-zinc-400">Downloads</h2>
          {pending.map((item) => (
            <div key={item.trackId} className="flex items-center justify-between gap-4 text-sm">
              <div>
                <p className="font-medium text-white">{item.title}</p>
                <p className="text-zinc-400">{item.status}</p>
                {item.error && <p className="text-red-400">{item.error}</p>}
              </div>
              {item.status === 'ready' && (
                <Link to={`/tracks/${item.trackId}`} className="btn-ghost">
                  Open
                </Link>
              )}
              {item.status === 'failed' && item.existingTrackId && (
                <Link to={`/tracks/${item.existingTrackId}`} className="btn-ghost">
                  Existing track
                </Link>
              )}
            </div>
          ))}
        </section>
      )}
    </div>
  );
}
