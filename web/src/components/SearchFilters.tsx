import type { Genre, Language } from '@/types';

interface SearchFiltersProps {
  q: string;
  genre: string;
  language: string;
  hasLyrics: string;
  sort: string;
  genres: Genre[];
  languages: Language[];
  onChange: (field: string, value: string) => void;
}

export function SearchFilters({
  q,
  genre,
  language,
  hasLyrics,
  sort,
  genres,
  languages,
  onChange,
}: SearchFiltersProps) {
  return (
    <div className="card grid gap-3 p-4 sm:grid-cols-2 lg:grid-cols-5">
      <input
        type="search"
        placeholder="Search tracks…"
        value={q}
        onChange={(event) => onChange('q', event.target.value)}
        className="input lg:col-span-2"
      />
      <select value={genre} onChange={(event) => onChange('genre', event.target.value)} className="input">
        <option value="">All genres</option>
        {genres.map((item) => (
          <option key={item.id} value={item.slug}>
            {item.name}
          </option>
        ))}
      </select>
      <select
        value={language}
        onChange={(event) => onChange('language', event.target.value)}
        className="input"
      >
        <option value="">All languages</option>
        {languages.map((item) => (
          <option key={item.id} value={item.code}>
            {item.name}
          </option>
        ))}
      </select>
      <select
        value={hasLyrics}
        onChange={(event) => onChange('has_lyrics', event.target.value)}
        className="input"
      >
        <option value="">Lyrics: any</option>
        <option value="true">With lyrics</option>
        <option value="false">Instrumental</option>
      </select>
      <select value={sort} onChange={(event) => onChange('sort', event.target.value)} className="input sm:col-span-2 lg:col-span-1">
        <option value="">Sort: default</option>
        <option value="title">Title</option>
        <option value="-created_at">Newest</option>
        <option value="play_count">Most played</option>
      </select>
    </div>
  );
}
