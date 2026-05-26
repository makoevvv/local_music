import { create } from 'zustand';
import type { TrackSummary } from '@/types';

interface PlayerState {
  currentTrack: TrackSummary | null;
  queue: TrackSummary[];
  isPlaying: boolean;
  isQueueOpen: boolean;
  volume: number;
  progress: number;
  duration: number;
  isLoading: boolean;
  playTrack: (track: TrackSummary, queue?: TrackSummary[]) => void;
  playQueue: (tracks: TrackSummary[], startIndex?: number) => void;
  togglePlay: () => void;
  pause: () => void;
  resume: () => void;
  next: () => TrackSummary | null;
  previous: () => TrackSummary | null;
  addToQueue: (track: TrackSummary) => void;
  removeFromQueue: (trackId: string) => void;
  clearQueue: () => void;
  setQueueOpen: (open: boolean) => void;
  setVolume: (volume: number) => void;
  setProgress: (progress: number) => void;
  setDuration: (duration: number) => void;
  setLoading: (loading: boolean) => void;
  setCurrentTrack: (track: TrackSummary | null) => void;
}

export const usePlayerStore = create<PlayerState>((set, get) => ({
  currentTrack: null,
  queue: [],
  isPlaying: false,
  isQueueOpen: false,
  volume: 0.85,
  progress: 0,
  duration: 0,
  isLoading: false,

  playTrack: (track, queue) => {
    const nextQueue = queue ?? get().queue;
    const existingIndex = nextQueue.findIndex((item) => item.id === track.id);
    const normalizedQueue =
      existingIndex >= 0
        ? nextQueue
        : [track, ...nextQueue.filter((item) => item.id !== track.id)];

    set({
      currentTrack: track,
      queue: normalizedQueue,
      isPlaying: true,
      progress: 0,
      isLoading: true,
    });
  },

  playQueue: (tracks, startIndex = 0) => {
    if (tracks.length === 0) return;
    const track = tracks[startIndex] ?? tracks[0];
    set({
      currentTrack: track,
      queue: tracks,
      isPlaying: true,
      progress: 0,
      isLoading: true,
    });
  },

  togglePlay: () => set((state) => ({ isPlaying: !state.isPlaying })),

  pause: () => set({ isPlaying: false }),

  resume: () => set({ isPlaying: true }),

  next: () => {
    const { currentTrack, queue } = get();
    if (!currentTrack || queue.length === 0) return null;
    const index = queue.findIndex((item) => item.id === currentTrack.id);
    const nextTrack = index >= 0 && index < queue.length - 1 ? queue[index + 1] : null;
    if (nextTrack) {
      set({ currentTrack: nextTrack, progress: 0, isPlaying: true, isLoading: true });
    } else {
      set({ isPlaying: false });
    }
    return nextTrack;
  },

  previous: () => {
    const { currentTrack, queue, progress } = get();
    if (!currentTrack) return null;
    if (progress > 3) {
      set({ progress: 0 });
      return currentTrack;
    }
    const index = queue.findIndex((item) => item.id === currentTrack.id);
    const prevTrack = index > 0 ? queue[index - 1] : null;
    if (prevTrack) {
      set({ currentTrack: prevTrack, progress: 0, isPlaying: true, isLoading: true });
    }
    return prevTrack;
  },

  addToQueue: (track) =>
    set((state) => ({
      queue: state.queue.some((item) => item.id === track.id)
        ? state.queue
        : [...state.queue, track],
    })),

  removeFromQueue: (trackId) =>
    set((state) => ({
      queue: state.queue.filter((item) => item.id !== trackId),
    })),

  clearQueue: () => set({ queue: [], currentTrack: null, isPlaying: false, progress: 0 }),

  setQueueOpen: (open) => set({ isQueueOpen: open }),

  setVolume: (volume) => set({ volume: Math.min(1, Math.max(0, volume)) }),

  setProgress: (progress) => set({ progress }),

  setDuration: (duration) => set({ duration }),

  setLoading: (loading) => set({ isLoading: loading }),

  setCurrentTrack: (track) => set({ currentTrack: track }),
}));
