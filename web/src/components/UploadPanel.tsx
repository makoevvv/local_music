import { FormEvent, useMemo, useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { Link } from 'react-router-dom';
import { getGenres, getLanguages } from '@/api/reference';
import {
  confirmUpload,
  sourceKey,
  uploadTrack,
  verifyUpload,
  type CandidateSource,
  type UploadMeta,
  type VerificationResult,
} from '@/api/upload';

const emptyMeta = (): UploadMeta => ({
  title: '',
  artists: [{ name: '', role: 'main' }],
  album: '',
  year: null,
  genres: [],
  language: '',
  instrumental: false,
  has_lyrics: true,
});

export function UploadPanel() {
  const [file, setFile] = useState<File | null>(null);
  const [cover, setCover] = useState<File | null>(null);
  const [uploadId, setUploadId] = useState<string | null>(null);
  const [meta, setMeta] = useState<UploadMeta>(emptyMeta());
  const [hasEmbeddedCover, setHasEmbeddedCover] = useState(false);
  const [verification, setVerification] = useState<VerificationResult | null>(null);
  const [selected, setSelected] = useState<string[]>([]);
  const [primary, setPrimary] = useState<string | null>(null);
  const [force, setForce] = useState(false);
  const [acceptSuggestions, setAcceptSuggestions] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [publishedId, setPublishedId] = useState<string | null>(null);
  const [alreadyExists, setAlreadyExists] = useState(false);

  const genres = useQuery({ queryKey: ['genres'], queryFn: getGenres });
  const languages = useQuery({ queryKey: ['languages'], queryFn: getLanguages });
  const coverPreview = useMemo(() => (cover ? URL.createObjectURL(cover) : null), [cover]);

  const updateMeta = (patch: Partial<UploadMeta>) => {
    setMeta((current) => ({ ...current, ...patch }));
    setVerification(null);
    setAcceptSuggestions(false);
    setPublishedId(null);
  };

  const onFile = async (next: File | null, coverFile: File | null = cover) => {
    setFile(next);
    setUploadId(null);
    setVerification(null);
    setPublishedId(null);
    setError(null);
    if (!next) {
      return;
    }
    setBusy(true);
    try {
      const created = await uploadTrack(next, null, coverFile);
      const parsed = created.parsed_meta;
      setUploadId(created.upload_id);
      setHasEmbeddedCover(Boolean(parsed.has_cover));
      setMeta({
        title: parsed.title ?? '',
        artists: parsed.artists?.length ? parsed.artists : [{ name: '', role: 'main' }],
        album: parsed.album ?? '',
        year: parsed.year ?? null,
        genres: parsed.genres ?? [],
        language: parsed.language ?? '',
        instrumental: Boolean(parsed.instrumental),
        has_lyrics: parsed.has_lyrics ?? true,
      });
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : 'Upload failed');
    } finally {
      setBusy(false);
    }
  };

  const onCover = async (next: File | null) => {
    setCover(next);
    setVerification(null);
    if (!next || !file) {
      return;
    }
    setBusy(true);
    setError(null);
    try {
      const created = await uploadTrack(file, normalizedMeta(meta), next);
      setUploadId(created.upload_id);
      setHasEmbeddedCover(true);
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : 'Cover upload failed');
    } finally {
      setBusy(false);
    }
  };

  const verify = async (event: FormEvent) => {
    event.preventDefault();
    if (!uploadId) {
      return;
    }
    setBusy(true);
    setError(null);
    try {
      const result = await verifyUpload(uploadId, normalizedMeta(meta));
      setVerification(result);
      const keys = result.candidate_sources.map(sourceKey);
      setSelected(keys);
      const index = result.primary_source_index ?? 0;
      setPrimary(keys[index] ?? keys[0] ?? null);
      setForce(false);
      setAcceptSuggestions(false);
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : 'Verification failed');
    } finally {
      setBusy(false);
    }
  };

  const publish = async () => {
    if (!uploadId || !verification) {
      return;
    }
    setBusy(true);
    setError(null);
    try {
      const result = await confirmUpload(uploadId, {
        meta: normalizedMeta(meta),
        accept_suggestions: acceptSuggestions,
        force,
        selected_source_ids: selected,
        primary_source_id: primary,
      });
      setPublishedId(result.track_id);
      setAlreadyExists(result.already_exists);
      if (result.rejected_source_ids.length > 0) {
        setError(`Some sources were rejected: ${result.rejected_source_ids.join(', ')}`);
      }
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : 'Publish failed');
    } finally {
      setBusy(false);
    }
  };

  const applySuggestions = () => {
    if (!verification) {
      return;
    }
    const suggestion = verification.suggestions;
    updateMeta({
      title: suggestion.title || meta.title,
      artists: suggestion.artist ? [{ name: suggestion.artist, role: 'main' }] : meta.artists,
      album: suggestion.album || meta.album,
      year: suggestion.year ?? meta.year,
      genres: suggestion.genres?.length ? suggestion.genres : meta.genres,
    });
    setAcceptSuggestions(true);
    setVerification(verification);
  };

  const lowTrustBlocked = verification?.trust_level === 'low' && !force;

  return (
    <form onSubmit={verify} className="space-y-6">
      <label
        className="flex cursor-pointer flex-col items-center justify-center rounded-xl border border-dashed border-surface-border bg-surface-overlay px-6 py-10 text-center"
        onDragOver={(event) => event.preventDefault()}
        onDrop={(event) => {
          event.preventDefault();
          const dropped = event.dataTransfer.files[0];
          if (dropped) {
            void onFile(dropped);
          }
        }}
      >
        <span className="text-sm text-zinc-300">Drop an audio file or choose one</span>
        <span className="mt-1 text-xs text-zinc-500">mp3, m4a, flac, ogg, opus, wav · up to 50 MB</span>
        <input
          type="file"
          accept="audio/*,.mp3,.m4a,.aac,.flac,.ogg,.opus,.wav"
          className="mt-4 text-sm text-zinc-400"
          onChange={(event) => void onFile(event.target.files?.[0] ?? null)}
        />
      </label>

      {file && (
        <div className="grid gap-4 sm:grid-cols-2">
          <label className="space-y-1 text-sm text-zinc-400">
            Title
            <input
              className="input"
              value={meta.title}
              onChange={(event) => updateMeta({ title: event.target.value })}
              required
            />
          </label>
          <label className="space-y-1 text-sm text-zinc-400">
            Artist
            <input
              className="input"
              value={meta.artists[0]?.name ?? ''}
              onChange={(event) =>
                updateMeta({ artists: [{ name: event.target.value, role: 'main' }] })
              }
              required
            />
          </label>
          <label className="space-y-1 text-sm text-zinc-400">
            Album
            <input
              className="input"
              value={meta.album ?? ''}
              onChange={(event) => updateMeta({ album: event.target.value })}
              placeholder="Leave empty to detect"
            />
          </label>
          <label className="space-y-1 text-sm text-zinc-400">
            Year
            <input
              className="input"
              type="number"
              value={meta.year ?? ''}
              onChange={(event) =>
                updateMeta({ year: event.target.value ? Number(event.target.value) : null })
              }
            />
          </label>
          <label className="space-y-1 text-sm text-zinc-400">
            Genres
            <input
              className="input"
              list="upload-genres"
              value={meta.genres.join(', ')}
              onChange={(event) =>
                updateMeta({
                  genres: event.target.value
                    .split(',')
                    .map((item) => item.trim())
                    .filter(Boolean),
                })
              }
            />
            <datalist id="upload-genres">
              {(genres.data ?? []).map((genre) => (
                <option key={genre.id} value={genre.name} />
              ))}
            </datalist>
          </label>
          <label className="space-y-1 text-sm text-zinc-400">
            Language
            <input
              className="input"
              list="upload-languages"
              value={meta.language ?? ''}
              onChange={(event) => updateMeta({ language: event.target.value })}
            />
            <datalist id="upload-languages">
              {(languages.data ?? []).map((language) => (
                <option key={language.code} value={language.code}>
                  {language.name}
                </option>
              ))}
            </datalist>
          </label>
          <label className="flex items-center gap-2 text-sm text-zinc-300">
            <input
              type="checkbox"
              checked={meta.instrumental}
              onChange={(event) =>
                updateMeta({ instrumental: event.target.checked, has_lyrics: !event.target.checked })
              }
            />
            Instrumental
          </label>
          <label className="space-y-1 text-sm text-zinc-400">
            Cover
            <input
              type="file"
              accept="image/jpeg,image/png,image/webp"
              className="block text-sm text-zinc-400"
              onChange={(event) => void onCover(event.target.files?.[0] ?? null)}
            />
          </label>
        </div>
      )}

      {(coverPreview || hasEmbeddedCover) && (
        <div className="flex items-center gap-3 text-sm text-zinc-400">
          {coverPreview ? (
            <img src={coverPreview} alt="" className="h-16 w-16 rounded-lg object-cover" />
          ) : (
            <span>Cover embedded in the file will be used.</span>
          )}
        </div>
      )}

      <div className="flex flex-wrap gap-3">
        <button type="submit" className="btn-primary" disabled={!uploadId || busy || !meta.title}>
          {busy ? 'Working…' : 'Check'}
        </button>
        <button
          type="button"
          className="btn-ghost"
          disabled={!verification || busy || lowTrustBlocked}
          onClick={() => void publish()}
        >
          Publish to library
        </button>
      </div>

      {error && <p className="text-sm text-red-400">{error}</p>}

      {verification && (
        <section className="space-y-4 rounded-xl border border-surface-border bg-surface-overlay p-4">
          <p className="text-sm text-zinc-300">
            Trust <span className="font-medium text-white">{verification.trust_level}</span>
            <span className="text-zinc-500"> · {verification.score.toFixed(2)}</span>
            {verification.sources_verification.length > 0 && (
              <span className="text-zinc-500"> · {verification.sources_verification.join(', ')}</span>
            )}
          </p>
          {verification.album_conflict && (
            <p className="text-sm text-amber-300">
              MusicBrainz album differs from the one you typed. You can apply the suggestion.
            </p>
          )}
          {verification.trust_level === 'none' && (
            <p className="text-sm text-zinc-400">The track will be marked unverified.</p>
          )}
          {verification.trust_level === 'low' && (
            <label className="flex items-center gap-2 text-sm text-zinc-300">
              <input type="checkbox" checked={force} onChange={(event) => setForce(event.target.checked)} />
              Publish anyway. Metadata may be wrong.
            </label>
          )}
          <button type="button" className="btn-ghost" onClick={applySuggestions}>
            Apply suggestion
          </button>
          {verification.candidate_sources.length === 0 ? (
            <p className="text-sm text-zinc-400">No public source matched. The index will only keep your file.</p>
          ) : (
            <ul className="space-y-3">
              {verification.candidate_sources.map((source) => (
                <SourceRow
                  key={sourceKey(source)}
                  source={source}
                  checked={selected.includes(sourceKey(source))}
                  primary={primary === sourceKey(source)}
                  onToggle={(checked) => {
                    const key = sourceKey(source);
                    setSelected((current) =>
                      checked ? [...current, key] : current.filter((item) => item !== key),
                    );
                    if (!checked && primary === key) {
                      setPrimary(null);
                    }
                    if (checked && !primary) {
                      setPrimary(key);
                    }
                  }}
                  onPrimary={() => {
                    const key = sourceKey(source);
                    setPrimary(key);
                    setSelected((current) => (current.includes(key) ? current : [...current, key]));
                  }}
                />
              ))}
            </ul>
          )}
        </section>
      )}

      {publishedId && (
        <p className="text-sm text-zinc-300">
          {alreadyExists ? 'Already in the library.' : 'Published.'}{' '}
          <Link to={`/tracks/${publishedId}`} className="text-accent">
            Open track
          </Link>
        </p>
      )}
    </form>
  );
}

function normalizedMeta(meta: UploadMeta): UploadMeta {
  return {
    ...meta,
    title: meta.title.trim(),
    album: meta.album?.trim() ? meta.album.trim() : null,
    language: meta.language?.trim() ? meta.language.trim() : null,
    year: meta.year || null,
    artists: meta.artists
      .map((artist) => ({ ...artist, name: artist.name.trim() }))
      .filter((artist) => artist.name),
  };
}

function SourceRow({
  source,
  checked,
  primary,
  onToggle,
  onPrimary,
}: {
  source: CandidateSource;
  checked: boolean;
  primary: boolean;
  onToggle: (checked: boolean) => void;
  onPrimary: () => void;
}) {
  return (
    <li className="flex items-start gap-3 text-sm">
      <input type="checkbox" checked={checked} onChange={(event) => onToggle(event.target.checked)} />
      <div className="min-w-0 flex-1">
        <p className="truncate text-white">{source.title}</p>
        <p className="truncate text-zinc-500">
          {source.kind}
          {source.channel ? ` · ${source.channel}` : ''} · {source.match.toFixed(2)}
        </p>
      </div>
      <label className="flex items-center gap-1 text-zinc-400">
        <input type="radio" checked={primary} onChange={onPrimary} />
        Primary
      </label>
    </li>
  );
}
