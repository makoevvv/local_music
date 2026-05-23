# 16. Индекс библиотеки и восстановление

Цель: иметь компактный, переносимый «слепок» всей библиотеки, по которому можно **с нуля** на новом сервере восстановить все треки, даже если аудиофайлы физически утеряны. Это делает миграцию между серверами безопасной и обратимой.

## 1. Концепция

В дополнение к таблицам БД хранится **library index** — машиночитаемый журнал источников каждого трека:
- для треков, скачанных из интернета — исходный URL, источник (`youtube`, `soundcloud`, `bandcamp`, ...), `source_id`;
- для треков, загруженных пользователем вручную — `audio_sha256`, `mbid` (если разрешён), исходное имя файла и оригинальные теги;
- метаданные (название, исполнители, альбом, обложка) — в нормализованном виде.

Индекс — это **отдельная сущность от storage**: storage можно потерять, индекс достаточно, чтобы пересобрать библиотеку.

## 2. Схема данных

### Новая таблица `track_sources`

Один трек может иметь несколько источников (например, был добавлен из YouTube, потом ту же запись пользователь загрузил с диска). Сохраняем все.

| Поле | Тип | Описание |
|---|---|---|
| id | uuid PK | |
| track_id | uuid FK tracks.id ON DELETE CASCADE | |
| source_kind | text not null | `youtube`, `soundcloud`, `bandcamp`, `direct_url`, `user_upload`, `unknown` |
| source_url | text null | прямая ссылка, если применимо |
| source_id | text null | id в источнике (например, youtube video id) |
| original_filename | text null | имя загруженного файла |
| original_tags | jsonb default '{}' | сырые ID3-теги из mutagen |
| added_by_user_id | uuid FK users.id | |
| added_at | timestamptz default now() | |
| recovery_priority | int default 100 | меньше → выше приоритет при восстановлении. Соглашение по умолчанию: tier 1 (CC/free) = 10, tier 2 (open public) = 30, tier 3 (user_upload) = 60, tier 4 (restricted) = 200. См. [`06-music-sourcing.md`](06-music-sourcing.md:1) §«Политика источников». |
| last_checked_at | timestamptz null | когда в последний раз ссылка успешно отдала аудио |
| last_status | text null | `ok`, `gone`, `geo_blocked`, `private`, `forbidden` |

Индексы:
- `idx_track_sources_track` (`track_id`).
- `idx_track_sources_kind_status` (`source_kind`, `last_status`).

`tracks.source_kind` / `tracks.source_url` / `tracks.source_id` остаются для «основного» источника (для UI), но **подробная история** живёт в `track_sources`.

### Поля в `tracks` для восстановления
Уже есть: `audio_sha256`, `mbid`, `isrc`, `file_format`, `duration_seconds`.

Дополнительно — рекомендуется (фиксируется в схеме):
- `acoustid_fingerprint` (text, опц.) — отпечаток chromaprint, чтобы можно было заново найти тот же recording в AcoustID без хранения файла.
- `cover_url_origin` (text, опц.) — откуда взяли обложку (Cover Art Archive, ytdl thumbnail, …).

Эти поля попадают в БД и в экспорт.

## 3. Экспорт индекса

### Формат
JSON Lines (`.jsonl`) — по одной строке на трек. Удобно для diff, append, частичной перезалив­ки.

```jsonl
{"id":"...uuid...","title":"Numb","artists":[{"name":"Linkin Park","role":"main","mbid":"..."}],"album":{"title":"Meteora","mbid":"...","is_single":false,"release_year":2003},"genres":["nu-metal","rock"],"languages":["en"],"duration":187,"audio_sha256":"...","mbid":"...","isrc":"...","acoustid_fingerprint":"AQAD...","cover_url_origin":"https://coverartarchive.org/...","sources":[{"kind":"youtube","url":"https://youtu.be/...","source_id":"kXYi...","added_at":"2026-01-15T10:11:00Z","last_status":"ok"},{"kind":"user_upload","original_filename":"linkin park - numb.mp3","added_at":"2026-02-02T22:00:00Z"}]}
```

### Содержимое экспорта
- `manifest.json` — метаданные дампа: версия схемы, дата, количество треков/альбомов/исполнителей, sha256 от `tracks.jsonl`.
- `tracks.jsonl` — основное.
- `users.jsonl` — пользователи (без паролей при экспорте по умолчанию; с паролями только с явным флагом `--include-secrets`).
- `playlists.jsonl` — плейлисты + связи (track_id ссылается на uuid треков; track_id стабилен).
- `plays.jsonl` (опц., большой) — история прослушиваний; можно исключить флагом `--no-plays`.
- `covers/` — папка с обложками (если хотим переносить вместе с индексом без повторного скачивания).

### CLI
```bash
# Полный экспорт
docker compose exec backend python -m app.cli index export \
  --out /data/exports/library-2026-05-23.tar.gz \
  [--include-covers] [--include-secrets] [--no-plays]

# Только манифест и треки (минимальный для восстановления)
docker compose exec backend python -m app.cli index export --minimal --out ...
```

Дамп архивируется (`tar.gz`) и хранится рядом с обычными бэкапами (см. [`09-infrastructure.md`](09-infrastructure.md:1)).

### Автоматический экспорт
Добавляется в крон (см. [`09-infrastructure.md`](09-infrastructure.md:1)):
- ежедневно — минимальный экспорт;
- еженедельно — полный с обложками.

## 4. Восстановление библиотеки

Сценарий: «чистый сервер, есть только `library-*.tar.gz`».

```bash
# 1. Поднять чистую систему
docker compose up -d
docker compose exec backend alembic upgrade head
docker compose exec backend python -m app.cli init-master   # создать мастера

# 2. Импорт индекса
docker compose exec backend python -m app.cli index import \
  --in /data/exports/library-2026-05-23.tar.gz \
  --mode skip-existing

# 3. Восстановление аудио
docker compose exec backend python -m app.cli library restore \
  [--strategy=best-source-first] [--concurrency=2] [--dry-run]
```

### Алгоритм `library restore`

Для каждого трека со статусом `missing_file=true`:
1. Сортируем `track_sources` по `recovery_priority` ASC и (`last_status='ok'` сначала).
2. Перебираем источники:
   - **`youtube`/`soundcloud`/`bandcamp`/`direct_url`** → `yt-dlp` загрузка → транскод в opus.
   - **`user_upload`** → не восстанавливается автоматически (файл у пользователя). Помечаем `needs_user_reupload`.
3. После скачивания считаем `audio_sha256` и сравниваем с сохранённым.
   - Совпадает → ✅ ставим `tracks.status='ready'`, привязываем файл.
   - Не совпадает → пробуем следующий источник; помечаем `last_status='checksum_mismatch'` для этого source.
4. Если все источники исчерпаны:
   - Пробуем `acoustid_fingerprint` → поиск в AcoustID → mbid → пробуем найти через YouTube/SoundCloud по `artist - title` (fuzzy).
   - Если ничего — статус трека `tracks.status='unrecoverable'`, попадает в admin-отчёт.

### Дряхлость источников
Фоновая задача `verify_sources` (раз в неделю) делает легковесную проверку:
- HEAD-запрос на источник, статус доступности.
- Обновляет `last_checked_at`, `last_status`.
- Не качает, не тратит трафик.

В UI master/admin видит счётчик «треков с протухшими источниками» и может проактивно их перекачать.

## 5. Стабильность идентификаторов

Чтобы экспорт/импорт работал между серверами без рассинхрона:
- UUID треков, плейлистов, альбомов, артистов **переносятся как есть**. Никаких авто-перегенераций.
- При импорте конфликт по `audio_sha256`: используется существующий локально track, его id переписывается в новых ссылках на старый id из дампа (mapping `imported_id → existing_id`). Mapping логируется.
- При импорте конфликт по UUID (есть локально с тем же id, но другой `audio_sha256`): импортируемая запись пропускается с предупреждением, требует ручного разрешения.

## 6. Минимальный «portable» режим

Для случая «хочу взять только индекс с собой, без сервера»:
- Утилита `python -m app.cli index export --minimal` создаёт один файл `library.jsonl.gz`.
- Файл валидирует JSON-схемой (положим её в `docs/schemas/library.schema.json` — TODO в этапе 4.2).

## 7. Расширения (на будущее)
- Подпись манифеста (HMAC секретом master) — защита от подмены при переносе.
- Дельта-экспорт (`since=<timestamp>`) — для инкрементальной синхронизации между двумя инстансами.
- Опциональная mirror-репликация второго сервера в режиме «холодный резерв» (через `index import --mode mirror` каждый час).

## 8. Влияние на существующие документы
- [`04-database-schema.md`](04-database-schema.md:1) — добавить таблицу `track_sources`, поля `tracks.acoustid_fingerprint`, `tracks.cover_url_origin`.
- [`05-api-spec.md`](05-api-spec.md:1) — добавить admin/master-эндпоинты: `POST /admin/index/export`, `POST /admin/library/restore`, `GET /admin/library/health` (статистика по источникам).
- [`09-infrastructure.md`](09-infrastructure.md:1) — добавить экспорт индекса в расписание бэкапов.
- [`12-roadmap.md`](12-roadmap.md:1) — добавить этап **4.2 «Index & Restore»** после 4.1.
- [`06-music-sourcing.md`](06-music-sourcing.md:1) — при создании трека из кандидата всегда писать запись в `track_sources` (не только в `tracks.source_*`).
- [`14-user-upload.md`](14-user-upload.md:1) — при ручной загрузке также писать `track_sources(kind='user_upload', original_filename, original_tags)`.

## 9. Что это даёт владельцу

- Переезд на новый сервер за несколько часов: достаточно унести `library-*.tar.gz`.
- Защита от потери диска: даже без бэкапа аудио, индекс позволит перекачать всё, что доступно в источниках.
- Прозрачность: видно, откуда каждый трек пришёл и жива ли ссылка.
- Дешёвый «холодный бэкап» — индекс много меньше аудио, его можно хранить где угодно (GitHub Releases приватного репо, личное облако, USB-флешка).
