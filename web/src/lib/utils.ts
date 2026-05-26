export function formatDuration(seconds: number | null | undefined): string {
  if (seconds == null || Number.isNaN(seconds)) return '—';
  const mins = Math.floor(seconds / 60);
  const secs = Math.floor(seconds % 60);
  return `${mins}:${secs.toString().padStart(2, '0')}`;
}

export function formatArtists(
  artists: { name: string; role?: string }[] | undefined,
): string {
  if (!artists || artists.length === 0) return 'Unknown artist';
  return artists.map((artist) => artist.name).join(', ');
}

export function cn(...classes: Array<string | false | null | undefined>): string {
  return classes.filter(Boolean).join(' ');
}
