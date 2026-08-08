# Архив задачи: Этап 4.2 — Index & Restore

**Дата:** 2026-08-08  
**Ветка:** `cursor/stage-4-2-index-restore-409a` (поверх `stage/4-search-download`)

## Что сделано

- Миграция `20260808_0005`: `track_sources`, `tracks.acoustid_fingerprint`, статус `unrecoverable`, backfill из `tracks.source_*`.
- Запись в `track_sources` при download из search и CLI `import-track`.
- CLI: `index export|import`, `library restore`, `verify-sources`.
- Admin API: `/admin/index/export|exports|import`, `/admin/library/restore|health`.
- Скрипт расписания `infra/scripts/export_index.sh`, том `/data/exports`.
- JSON Schema `docs/schemas/library.schema.json`.

## Следующий этап

Этап **4.1** — ручная загрузка и AcoustID ([`14-user-upload.md`](../14-user-upload.md:1)).
