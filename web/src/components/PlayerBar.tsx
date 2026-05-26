import { useEffect, useRef } from 'react';
import { logPlay } from '@/api/tracks';
import { QueuePanel } from '@/components/QueuePanel';
import { useStreamUrl } from '@/hooks/useStreamUrl';
import { formatArtists, formatDuration } from '@/lib/utils';
import { usePlayerStore } from '@/store/playerStore';
import { useAuthStore } from '@/store/authStore';

export function PlayerBar() {
  const audioRef = useRef<HTMLAudioElement>(null);
  const playLoggedRef = useRef<string | null>(null);

  const isAuthenticated = useAuthStore((state) => state.isAuthenticated);
  const currentTrack = usePlayerStore((state) => state.currentTrack);
  const isPlaying = usePlayerStore((state) => state.isPlaying);
  const volume = usePlayerStore((state) => state.volume);
  const progress = usePlayerStore((state) => state.progress);
  const duration = usePlayerStore((state) => state.duration);
  const isLoading = usePlayerStore((state) => state.isLoading);
  const isQueueOpen = usePlayerStore((state) => state.isQueueOpen);

  const togglePlay = usePlayerStore((state) => state.togglePlay);
  const next = usePlayerStore((state) => state.next);
  const previous = usePlayerStore((state) => state.previous);
  const setVolume = usePlayerStore((state) => state.setVolume);
  const setProgress = usePlayerStore((state) => state.setProgress);
  const setDuration = usePlayerStore((state) => state.setDuration);
  const setLoading = usePlayerStore((state) => state.setLoading);
  const setQueueOpen = usePlayerStore((state) => state.setQueueOpen);

  const { streamUrl, isLoading: streamLoading, error: streamError } = useStreamUrl(
    isAuthenticated ? currentTrack?.id ?? null : null,
  );

  useEffect(() => {
    const audio = audioRef.current;
    if (!audio) return;
    audio.volume = volume;
  }, [volume]);

  useEffect(() => {
    const audio = audioRef.current;
    if (!audio || !streamUrl) return;

    audio.src = streamUrl;
    audio.load();
    setLoading(true);

    if (isPlaying) {
      void audio.play().catch(() => {
        setLoading(false);
      });
    }
  }, [streamUrl, currentTrack?.id, setLoading]);

  useEffect(() => {
    const audio = audioRef.current;
    if (!audio) return;

    if (isPlaying) {
      void audio.play().catch(() => undefined);
    } else {
      audio.pause();
    }
  }, [isPlaying]);

  useEffect(() => {
    setLoading(streamLoading);
  }, [streamLoading, setLoading]);

  useEffect(() => {
    if (!currentTrack || !isPlaying) return;
    if (playLoggedRef.current === currentTrack.id) return;
    playLoggedRef.current = currentTrack.id;
    void logPlay(currentTrack.id).catch(() => undefined);
  }, [currentTrack, isPlaying]);

  if (!isAuthenticated || !currentTrack) {
    return null;
  }

  const handleSeek = (value: number) => {
    const audio = audioRef.current;
    if (!audio) return;
    audio.currentTime = value;
    setProgress(value);
  };

  return (
    <>
      <QueuePanel />
      <footer className="fixed bottom-0 left-0 right-0 z-30 border-t border-surface-border bg-surface-raised/95 backdrop-blur">
        <audio
          ref={audioRef}
          onTimeUpdate={(event) => setProgress(event.currentTarget.currentTime)}
          onLoadedMetadata={(event) => setDuration(event.currentTarget.duration || 0)}
          onCanPlay={() => setLoading(false)}
          onWaiting={() => setLoading(true)}
          onPlaying={() => setLoading(false)}
          onEnded={() => next()}
          onError={() => setLoading(false)}
        />

        <div className="mx-auto max-w-6xl px-4 py-3">
          <div className="mb-2 flex items-center gap-3">
            <span className="w-10 text-xs tabular-nums text-zinc-500">{formatDuration(progress)}</span>
            <input
              type="range"
              min={0}
              max={duration || currentTrack.duration_seconds || 0}
              step={0.1}
              value={progress}
              onChange={(event) => handleSeek(Number(event.target.value))}
              className="flex-1"
            />
            <span className="w-10 text-right text-xs tabular-nums text-zinc-500">
              {formatDuration(duration || currentTrack.duration_seconds)}
            </span>
          </div>

          <div className="flex items-center gap-4">
            <div className="min-w-0 flex-1">
              <p className="truncate font-medium text-white">{currentTrack.title}</p>
              <p className="truncate text-sm text-zinc-400">{formatArtists(currentTrack.artists)}</p>
              {streamError && <p className="truncate text-xs text-red-400">{streamError}</p>}
            </div>

            <div className="flex items-center gap-2">
              <button type="button" className="btn-icon" onClick={() => previous()} aria-label="Previous">
                ⏮
              </button>
              <button
                type="button"
                className="inline-flex h-11 w-11 items-center justify-center rounded-full bg-white text-black hover:bg-zinc-200"
                onClick={togglePlay}
                aria-label={isPlaying ? 'Pause' : 'Play'}
              >
                {isLoading ? '…' : isPlaying ? '⏸' : '▶'}
              </button>
              <button type="button" className="btn-icon" onClick={() => next()} aria-label="Next">
                ⏭
              </button>
            </div>

            <div className="hidden items-center gap-2 sm:flex">
              <span className="text-xs text-zinc-500">🔊</span>
              <input
                type="range"
                min={0}
                max={1}
                step={0.01}
                value={volume}
                onChange={(event) => setVolume(Number(event.target.value))}
                className="w-24"
              />
            </div>

            <button
              type="button"
              className="btn-ghost px-3"
              onClick={() => setQueueOpen(!isQueueOpen)}
            >
              Queue
            </button>
          </div>
        </div>
      </footer>
    </>
  );
}
