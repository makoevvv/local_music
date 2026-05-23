# 02. Архитектура

## 1. Общая схема

```
┌─────────────┐   ┌─────────────┐   ┌──────────────┐
│  Web (SPA)  │   │  iOS app    │   │ Android app  │
│  React+TS   │   │  SwiftUI    │   │  Compose     │
└──────┬──────┘   └──────┬──────┘   └──────┬───────┘
       │ HTTPS           │ HTTPS           │ HTTPS
       └────────┬────────┴────────┬────────┘
                │                 │
        ┌───────▼─────────────────▼───────┐
        │  Reverse proxy (Caddy / Nginx)  │  ← TLS, статика web
        └───────────────┬─────────────────┘
                        │
        ┌───────────────▼─────────────────┐
        │   FastAPI app (uvicorn)         │
        │   - auth, catalog, playlists    │
        │   - search, sourcing            │
        │   - vibe (recommendations)      │
        │   - stream (range requests)     │
        └──┬──────────┬─────────┬────────┬┘
           │          │         │        │
       ┌───▼──┐  ┌───▼───┐  ┌──▼────┐ ┌─▼────────┐
       │ PG   │  │ Redis │  │ Worker│ │ Storage  │
       │ 16   │  │       │  │ (RQ/  │ │ local FS │
       │      │  │ cache │  │ Celery│ │  или     │
       │      │  │ queue │  │ )     │ │ MinIO/S3 │
       └──────┘  └───────┘  └───┬───┘ └──────────┘
                                │
                       внешние API:
                       ┌────────┴─────────┐
                       │ yt-dlp           │
                       │ MusicBrainz      │
                       │ Last.fm          │
                       │ Shazam (RapidAPI)│
                       └──────────────────┘
```

## 2. Компоненты

### 2.1 Backend (FastAPI)
- **Слои:**
  - `api/` — роутеры (HTTP-эндпоинты, Pydantic-схемы).
  - `services/` — бизнес-логика (auth, catalog, vibe, sourcing).
  - `repositories/` — доступ к БД (SQLAlchemy 2.x async).
  - `models/` — ORM-модели.
  - `workers/` — фоновые задачи (загрузка, нормализация, метаданные).
  - `core/` — конфиг, security, logging, deps.
- **Принципы:** dependency injection через FastAPI `Depends`, типизация (mypy strict), pydantic-settings для конфига.

### 2.2 Worker
- Очередь: **Redis + RQ** (проще Celery, для одной машины достаточно).
- Задачи:
  - `download_track(candidate_id)` — yt-dlp + ffmpeg.
  - `enrich_metadata(track_id)` — MusicBrainz, Last.fm.
  - `compute_audio_features(track_id)` — длительность, BPM, энергия (через `librosa` или `essentia` опционально).
  - `cleanup_temp()` — удаление временных файлов.

### 2.3 БД — PostgreSQL 16
- Основное хранилище: users, tracks, artists, albums, genres, playlists, plays, likes, etc.
- Расширения: `pg_trgm` (нечёткий поиск), `unaccent`.
- Возможно `pgvector` — для эмбеддингов аудио на будущее.

### 2.4 Кеш — Redis 7
- Сессии (опционально, если не чисто JWT).
- Кеш ответов внешних API (MusicBrainz, Last.fm — у них rate limits).
- Очередь задач (RQ).
- Pub/Sub для уведомлений (websocket о статусе загрузки).

### 2.5 Storage
- **MVP:** локальная FS — `STORAGE_LOCAL_PATH=/data/storage`.
  - Структура: `storage/tracks/{track_id[:2]}/{track_id}.{ext}` (sharding по префиксу UUID).
- **Будущее:** MinIO (S3-совместимый) — для горизонтального масштабирования.
- Аудио хранится в `opus` (96 kbps) — компромисс качество/размер.
- Оригинал может удаляться после транскода (опционально).

### 2.6 Reverse proxy
- **Caddy** — выбран за автоматический HTTPS и простой конфиг (1 файл).
- Раздаёт статику web-клиента + проксирует `/api/*` → FastAPI.
- Поддержка `Range` заголовков для стриминга.

### 2.7 Web-клиент
- React 18 + TypeScript + Vite.
- Состояние: Zustand (легче Redux).
- Роутинг: React Router.
- HTTP: `axios` или `fetch` + React Query.
- Плеер: HTML5 `<audio>` + кастомный UI; обёртка через хук `usePlayer`.

### 2.8 iOS-клиент
- SwiftUI, минимальная версия iOS 16.
- Сетевой слой: `URLSession` + `async/await`.
- Плеер: `AVPlayer` (поддержка background audio, Now Playing).
- Доставка: TestFlight (внутренние тестеры) — см. [`10-mobile-apps.md`](10-mobile-apps.md:1).

## 3. Поток: «пользователь ищет и добавляет трек»

```
1. POST /api/search { query: "Linkin Park - Numb" }
   → backend ищет в кеше → если нет, дёргает yt-dlp в headless-режиме
   → возвращает кандидатов (10 шт): {id, title, artist, duration, source, thumb}

2. POST /api/tracks/from-candidate { candidate_id }
   → backend создаёт запись Track(status=downloading), кладёт задачу в RQ
   → возвращает {track_id, status: "downloading"}

3. Worker: download_track(candidate_id)
   → yt-dlp скачивает bestaudio
   → ffmpeg транскодит в opus 96kbps
   → хеширует аудио, проверяет дубликаты
   → сохраняет файл, обновляет Track(status=ready, file_path, duration, ...)
   → публикует событие в Redis Pub/Sub

4. Worker: enrich_metadata(track_id)
   → MusicBrainz: ищет MBID, альбом, год
   → Last.fm: жанры, теги
   → обновляет Track + связи Artist/Album/Genre

5. Frontend получает через WS обновление статуса
   → пользователь видит «Готово» → может слушать
```

## 4. Поток: «волна»

См. [`07-vibe-recommendations.md`](07-vibe-recommendations.md:1).

## 5. Деплой

См. [`09-infrastructure.md`](09-infrastructure.md:1).

## 6. Решения и альтернативы

| Решение | Выбрано | Альтернатива | Почему |
|---|---|---|---|
| Backend | FastAPI | Django, Flask | async, OpenAPI, типизация, скорость разработки |
| ORM | SQLAlchemy 2 async | Tortoise, Django ORM | стандарт, гибкость |
| Очередь | RQ | Celery, Dramatiq | проще, хватает для одной машины |
| БД | PostgreSQL | SQLite, MySQL | full-text, pg_trgm, pgvector |
| Web | React+Vite | Next.js, Vue, Svelte | привычный стек, SPA достаточно |
| Прокси | Caddy | Nginx, Traefik | авто-HTTPS, минимальный конфиг |
| Storage | local FS | S3/MinIO сразу | проще на старте, MinIO как опция |
