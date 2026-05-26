import { apiRequest } from '@/api/client';
import type { Genre, Language } from '@/types';

export async function getGenres(): Promise<Genre[]> {
  const data = await apiRequest<Genre[] | { items: Genre[] }>('/api/v1/genres');
  return Array.isArray(data) ? data : data.items;
}

export async function getLanguages(): Promise<Language[]> {
  const data = await apiRequest<Language[] | { items: Language[] }>('/api/v1/languages');
  return Array.isArray(data) ? data : data.items;
}
