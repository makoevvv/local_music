import { FormEvent, useState } from 'react';
import { Link } from 'react-router-dom';
import { apiFormRequest, apiRequest } from '@/api/client';

interface ImportJob {
  id: string;
  provider: string;
  status: string;
  total_tracks: number;
  resolved_tracks: number;
  ambiguous_tracks: number;
  failed_tracks: number;
}

interface ImportItem {
  id: string;
  title: string;
  artist: string;
  playlist_name: string;
  status: string;
  candidates: { source_key?: string; title?: string; kind?: string; match?: number }[];
}

export function ImportPage() {
  const [job, setJob] = useState<ImportJob | null>(null);
  const [items, setItems] = useState<ImportItem[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const onSubmit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    const form = new FormData(event.currentTarget);
    const file = form.get('file');
    if (!(file instanceof File) || file.size === 0) {
      return;
    }
    setBusy(true);
    setError(null);
    try {
      const created = await apiFormRequest<ImportJob>('/api/v1/import/file', form);
      setJob(created);
      const rows = await apiRequest<ImportItem[]>(`/api/v1/import/jobs/${created.id}/items`);
      setItems(rows);
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : 'Import failed');
    } finally {
      setBusy(false);
    }
  };

  const choose = async (item: ImportItem, sourceKey: string) => {
    if (!job) {
      return;
    }
    setBusy(true);
    try {
      await apiRequest(`/api/v1/import/jobs/${job.id}/items/${item.id}/resolve`, {
        method: 'POST',
        body: { source_key: sourceKey },
      });
      const rows = await apiRequest<ImportItem[]>(`/api/v1/import/jobs/${job.id}/items`);
      setItems(rows);
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : 'Could not resolve the track');
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-semibold text-white">Import</h1>
        <p className="mt-1 text-sm text-zinc-400">
          Upload a CSV or JSON export. Confident matches are added automatically. Unclear ones stay in a queue.
        </p>
      </div>
      <form onSubmit={(event) => void onSubmit(event)} className="space-y-3">
        <input name="file" type="file" accept=".csv,.json,text/csv,application/json" className="text-sm text-zinc-300" />
        <input type="hidden" name="mode" value="add" />
        <button type="submit" className="btn-primary" disabled={busy}>
          {busy ? 'Importing…' : 'Import file'}
        </button>
      </form>
      {error && <p className="text-sm text-red-400">{error}</p>}
      {job && (
        <p className="text-sm text-zinc-300">
          {job.status}: {job.resolved_tracks} resolved, {job.ambiguous_tracks} need a choice, {job.failed_tracks} failed.
        </p>
      )}
      <ul className="space-y-3">
        {items.map((item) => (
          <li key={item.id} className="rounded-xl border border-surface-border bg-surface-overlay p-4 text-sm">
            <p className="text-white">
              {item.artist} — {item.title}
            </p>
            <p className="text-zinc-500">
              {item.playlist_name} · {item.status}
            </p>
            {item.status === 'ambiguous' &&
              item.candidates.map((candidate) =>
                candidate.source_key ? (
                  <button
                    key={candidate.source_key}
                    type="button"
                    className="btn-ghost mt-2"
                    onClick={() => void choose(item, candidate.source_key as string)}
                  >
                    Use {candidate.kind} {candidate.title}
                  </button>
                ) : null,
              )}
          </li>
        ))}
      </ul>
      <Link to="/playlists" className="text-sm text-accent">
        Open playlists
      </Link>
    </div>
  );
}
