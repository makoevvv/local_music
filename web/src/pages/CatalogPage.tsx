import { useMemo, useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { getGenres, getLanguages } from '@/api/reference';
import { getTracks } from '@/api/tracks';
import { SearchFilters } from '@/components/SearchFilters';
import { TrackList } from '@/components/TrackList';
import { usePlayerStore } from '@/store/playerStore';

const PAGE_SIZE = 20;

export function CatalogPage() {
  const [page, setPage] = useState(1);
  const [filters, setFilters] = useState({
    q: '',
    genre: '',
    language: '',
    has_lyrics: '',
    sort: '',
  });

  const playQueue = usePlayerStore((state) => state.playQueue);

  const queryParams = useMemo(
    () => ({
      page,
      page_size: PAGE_SIZE,
      q: filters.q || undefined,
      genre: filters.genre || undefined,
      language: filters.language || undefined,
      has_lyrics:
        filters.has_lyrics === '' ? undefined : filters.has_lyrics === 'true',
      sort: filters.sort || undefined,
    }),
    [page, filters],
  );

  const { data: genres = [] } = useQuery({ queryKey: ['genres'], queryFn: getGenres });
  const { data: languages = [] } = useQuery({ queryKey: ['languages'], queryFn: getLanguages });

  const { data, isLoading, isError, error } = useQuery({
    queryKey: ['tracks', queryParams],
    queryFn: () => getTracks(queryParams),
  });

  const tracks = data?.items ?? [];
  const total = data?.total ?? tracks.length;
  const totalPages = Math.max(1, Math.ceil(total / PAGE_SIZE));

  const handleFilterChange = (field: string, value: string) => {
    setPage(1);
    setFilters((prev) => ({ ...prev, [field]: value }));
  };

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-semibold text-white">Catalog</h1>
        <p className="mt-1 text-sm text-zinc-400">Browse and play tracks from your library</p>
      </div>

      <SearchFilters
        q={filters.q}
        genre={filters.genre}
        language={filters.language}
        hasLyrics={filters.has_lyrics}
        sort={filters.sort}
        genres={genres}
        languages={languages}
        onChange={handleFilterChange}
      />

      {isLoading ? (
        <div className="card flex min-h-40 items-center justify-center p-8 text-sm text-zinc-400">
          Loading tracks…
        </div>
      ) : isError ? (
        <div className="card p-6 text-sm text-red-400">
          {error instanceof Error ? error.message : 'Failed to load tracks'}
        </div>
      ) : (
        <>
          <div className="flex items-center justify-between gap-4">
            <p className="text-sm text-zinc-500">{total} tracks</p>
            {tracks.length > 0 && (
              <button
                type="button"
                className="btn-ghost px-3"
                onClick={() => playQueue(tracks)}
              >
                Play all
              </button>
            )}
          </div>
          <TrackList tracks={tracks} />
          {totalPages > 1 && (
            <div className="flex items-center justify-center gap-3">
              <button
                type="button"
                className="btn-ghost"
                disabled={page <= 1}
                onClick={() => setPage((value) => value - 1)}
              >
                Previous
              </button>
              <span className="text-sm text-zinc-400">
                Page {page} of {totalPages}
              </span>
              <button
                type="button"
                className="btn-ghost"
                disabled={page >= totalPages}
                onClick={() => setPage((value) => value + 1)}
              >
                Next
              </button>
            </div>
          )}
        </>
      )}
    </div>
  );
}
