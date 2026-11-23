# Архив задачи: Этап 4.3 — внешние импорты

**Дата:** 2026-11-24  
**Ветка:** `cursor/stage-4-3-external-imports-1140`

## Что сделано

- Таблицы `external_accounts`, `import_jobs`, `import_items`, поле `playlists.metadata`.
- CSV/JSON, Spotify OAuth и токен Яндекса. Apple Music не делался: в roadmap он опционален.
- Резолвер: ISRC, локальный fuzzy, автозагрузка при score ≥ порога, иначе `ambiguous`.
- Повтор того же файла в том же режиме возвращает существующий job.
- Токены шифруются AES-GCM.

## Следующий этап

Этап **5** — «Моя волна».
