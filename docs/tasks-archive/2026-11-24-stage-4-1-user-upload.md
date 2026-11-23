# Архив задачи: Этап 4.1 — ручная загрузка и верификация

**Дата:** 2026-11-24  
**Ветка:** `cursor/stage-4-1-user-upload-1140` (поверх `cursor/stage-4-2-index-restore-409a`)

## Что сделано

- `POST /tracks/upload`, `GET /tracks/upload/{id}/verify`, `POST /tracks/upload/{id}/confirm`.
- Теги через mutagen, отпечаток через `fpcalc`, AcoustID при наличии `ACOUSTID_API_KEY`.
- Уровни доверия, разрешение альбома по primary-type, `is_single` только для подтверждённого Single.
- Поиск YouTube/SoundCloud и запись в `track_sources`: primary 10, запасные 20, `user_upload` 100.
- На confirm публичный источник скачивается и сверяется по chromaprint (≥ 0.97).
- CLI/RQ: `cleanup-uploads`, `reconcile-albums`, `match-user-uploads`.
- Web: вкладки Find online / Upload file, бейдж unverified.

## Следующий этап

Этап **4.3** — внешние импорты ([`17-external-imports.md`](../17-external-imports.md:1)).
