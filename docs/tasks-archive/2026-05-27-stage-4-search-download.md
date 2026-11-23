# Архив: этап 4 — поиск и загрузка из интернета

**Период:** 2026-05-27  
**Ветка:** `stage/4-search-download`  
**Статус:** реализовано локально, DoD проверен (search → Add → ready в каталоге).

## Сделано

- Миграция `search_candidates`, `tracks.metadata` (JSONB).
- API: `POST /search`, `POST /tracks/from-candidate`, `GET /tracks/{id}/status`, WebSocket `/api/v1/ws/tracks`.
- RQ worker `download_track_job`, дедуп по `audio_sha256`.
- yt-dlp + MusicBrainz/Last.fm enrichment.
- Web: `SearchPage`, прогресс загрузки.
- Docker: `worker`, `ytdlp-pot`, профиль `proxy` (sing-box), `YTDLP_PROXY`.

## Не входило в этап

- Таблица `track_sources` и library index export/import — **этап 4.2**.
- Ручная загрузка + AcoustID — **этап 4.1**.

## Заметки

- Использовать `docker compose -p local_music` чтобы не дублировать postgres на :5432.
- PO Token: `YTDLP_POT_BASE_URL=http://ytdlp-pot:4416` (по умолчанию в compose).
