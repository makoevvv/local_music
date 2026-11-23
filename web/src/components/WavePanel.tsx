import { useEffect, useRef, useState } from 'react';
import {
  listVibePresets,
  nextVibe,
  saveVibePreset,
  sendVibeFeedback,
  startVibe,
  toTrackSummary,
  type VibePreset,
  type VibeSettings,
} from '@/api/vibe';
import { usePlayerStore } from '@/store/playerStore';
import type { TrackSummary } from '@/types';

const MOODS = ['neutral', 'calm', 'energetic', 'sad', 'happy', 'focus', 'party'] as const;
const MODES = ['mixed', 'familiar', 'discover'] as const;

const DEFAULT_SETTINGS: VibeSettings = {
  mood: 'neutral',
  genres: [],
  languages: [],
  mode: 'mixed',
  explicit_allowed: true,
  no_lyrics: false,
};

function splitList(value: string): string[] {
  return value
    .split(',')
    .map((item) => item.trim())
    .filter(Boolean);
}

export function WavePanel() {
  const [settings, setSettings] = useState<VibeSettings>(DEFAULT_SETTINGS);
  const [genresText, setGenresText] = useState('');
  const [languagesText, setLanguagesText] = useState('');
  const [presetName, setPresetName] = useState('');
  const [presets, setPresets] = useState<VibePreset[]>([]);
  const [sessionId, setSessionId] = useState<string | null>(null);
  const [queue, setQueue] = useState<TrackSummary[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const playedRef = useRef(new Set<string>());

  const playQueue = usePlayerStore((state) => state.playQueue);
  const clearQueue = usePlayerStore((state) => state.clearQueue);
  const currentTrack = usePlayerStore((state) => state.currentTrack);
  const progress = usePlayerStore((state) => state.progress);
  const duration = usePlayerStore((state) => state.duration);

  useEffect(() => {
    void listVibePresets()
      .then(setPresets)
      .catch(() => setPresets([]));
  }, []);

  useEffect(() => {
    if (!sessionId || !currentTrack || duration <= 0) return;
    if (progress / duration < 0.5) return;
    if (playedRef.current.has(currentTrack.id)) return;
    playedRef.current.add(currentTrack.id);
    void sendVibeFeedback(sessionId, currentTrack.id, 'played').catch(() => {
      playedRef.current.delete(currentTrack.id);
    });
  }, [sessionId, currentTrack, progress, duration]);

  const currentSettings = (): VibeSettings => ({
    ...settings,
    genres: splitList(genresText),
    languages: splitList(languagesText),
  });

  const applyQueue = (tracks: TrackSummary[]) => {
    setQueue(tracks);
    if (tracks.length > 0) {
      playQueue(tracks);
      return;
    }
    clearQueue();
    setError('No tracks match this wave.');
  };

  const start = async () => {
    setBusy(true);
    setError(null);
    try {
      const response = await startVibe(currentSettings());
      setSessionId(response.session_id);
      applyQueue(response.queue.map(toTrackSummary));
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : 'Could not start the wave');
    } finally {
      setBusy(false);
    }
  };

  const react = async (action: 'like' | 'dislike' | 'skip') => {
    if (!sessionId || !currentTrack) return;
    setBusy(true);
    setError(null);
    try {
      await sendVibeFeedback(sessionId, currentTrack.id, action);
      const response = await nextVibe(sessionId);
      applyQueue(response.queue.map(toTrackSummary));
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : 'Could not update the wave');
    } finally {
      setBusy(false);
    }
  };

  const savePreset = async () => {
    const name = presetName.trim();
    if (!name) return;
    setError(null);
    try {
      const saved = await saveVibePreset(name, currentSettings());
      setPresets((current) => [saved, ...current.filter((item) => item.id !== saved.id)]);
      setPresetName('');
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : 'Could not save the preset');
    }
  };

  const applyPreset = (preset: VibePreset) => {
    const next = { ...DEFAULT_SETTINGS, ...preset.settings };
    setSettings(next);
    setGenresText(next.genres.join(', '));
    setLanguagesText(next.languages.join(', '));
  };

  return (
    <section className="card space-y-4 p-4">
      <div>
        <h2 className="text-lg font-semibold text-white">My wave</h2>
        <p className="mt-1 text-sm text-zinc-400">
          An endless queue for the current mood. Like, dislike, and skip change the next batch.
        </p>
      </div>

      <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
        <label className="space-y-1 text-sm text-zinc-400">
          Mood
          <select
            className="input"
            value={settings.mood}
            onChange={(event) => setSettings((current) => ({ ...current, mood: event.target.value }))}
          >
            {MOODS.map((mood) => (
              <option key={mood} value={mood}>
                {mood}
              </option>
            ))}
          </select>
        </label>
        <label className="space-y-1 text-sm text-zinc-400">
          Mode
          <select
            className="input"
            value={settings.mode}
            onChange={(event) => setSettings((current) => ({ ...current, mode: event.target.value }))}
          >
            {MODES.map((mode) => (
              <option key={mode} value={mode}>
                {mode}
              </option>
            ))}
          </select>
        </label>
        <label className="space-y-1 text-sm text-zinc-400">
          Genres
          <input
            className="input"
            value={genresText}
            placeholder="rock, ambient"
            onChange={(event) => setGenresText(event.target.value)}
          />
        </label>
        <label className="space-y-1 text-sm text-zinc-400">
          Languages
          <input
            className="input"
            value={languagesText}
            placeholder="en, ru"
            onChange={(event) => setLanguagesText(event.target.value)}
          />
        </label>
      </div>

      <div className="flex flex-wrap items-center gap-4 text-sm text-zinc-300">
        <label className="flex items-center gap-2">
          <input
            type="checkbox"
            checked={settings.explicit_allowed}
            onChange={(event) =>
              setSettings((current) => ({ ...current, explicit_allowed: event.target.checked }))
            }
          />
          Explicit
        </label>
        <label className="flex items-center gap-2">
          <input
            type="checkbox"
            checked={settings.no_lyrics}
            onChange={(event) =>
              setSettings((current) => ({ ...current, no_lyrics: event.target.checked }))
            }
          />
          Instrumental only
        </label>
        <button type="button" className="btn-primary" disabled={busy} onClick={() => void start()}>
          Start wave
        </button>
        <button
          type="button"
          className="btn-ghost"
          disabled={busy || !sessionId || !currentTrack}
          onClick={() => void react('like')}
        >
          Like
        </button>
        <button
          type="button"
          className="btn-ghost"
          disabled={busy || !sessionId || !currentTrack}
          onClick={() => void react('dislike')}
        >
          Dislike
        </button>
        <button
          type="button"
          className="btn-ghost"
          disabled={busy || !sessionId || !currentTrack}
          onClick={() => void react('skip')}
        >
          Skip
        </button>
      </div>

      <div className="flex flex-wrap items-center gap-2">
        <input
          className="input max-w-xs"
          value={presetName}
          placeholder="Preset name"
          onChange={(event) => setPresetName(event.target.value)}
        />
        <button type="button" className="btn-ghost" onClick={() => void savePreset()}>
          Save preset
        </button>
        {presets.map((preset) => (
          <button
            key={preset.id}
            type="button"
            className="btn-ghost"
            onClick={() => applyPreset(preset)}
          >
            {preset.name}
          </button>
        ))}
      </div>

      {queue.length > 0 && (
        <ol className="space-y-1 text-sm text-zinc-300">
          {queue.map((track, index) => (
            <li key={track.id}>
              {index + 1}. {track.title}
              {track.artists[0] ? ` — ${track.artists[0].name}` : ''}
            </li>
          ))}
        </ol>
      )}

      {error && <p className="text-sm text-red-400">{error}</p>}
    </section>
  );
}
