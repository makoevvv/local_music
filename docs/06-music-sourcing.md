# 06. Поиск и загрузка музыки

## Идея
Пользователь вводит запрос → backend ищет в открытых источниках → пользователь выбирает кандидата → backend асинхронно скачивает, нормализует и кладёт в общую библиотеку. Дубликаты исключаются по аудио-хешу.

## Политика источников

> Сервис — личный, некоммерческий, для узкого круга. Юридические/копирайт-аспекты в проекте **не учитываются** (см. [`00-overview.md`](00-overview.md:1)). Приоритет всё равно — открытые и бесплатные источники, потому что они стабильнее, быстрее и не требуют дополнительных шагов. Закрытые/«пиратские» источники допустимы как **fallback** только если открытых нет.

Каждому источнику присваивается **priority tier** — используется в [`14-user-upload.md`](14-user-upload.md:1) (source matching), [`16-library-index-and-restore.md`](16-library-index-and-restore.md:1) (`track_sources.recovery_priority`) и track resolver-е из [`17-external-imports.md`](17-external-imports.md:1).

| Tier | Категория | Примеры | Поведение |
|---|---|---|---|
| 1 | Free & open (Creative Commons / артистом выложено в свободный доступ) | Bandcamp (free tracks), SoundCloud (Original/CC), Free Music Archive, Jamendo, archive.org, MusicBrainz Cover Art | приоритет №1 для авто-загрузки, primary в `track_sources` |
| 2 | Open public (бесплатные, но без CC-лицензии) | YouTube, YouTube Music, SoundCloud (обычные треки), Bandcamp (платные стримы), Vimeo | основной массовый источник; авто-загрузка при уверенном матче |
| 3 | User upload | ручная загрузка пользователя | используется как primary только если tier 1–2 не нашли совпадения; см. [`14-user-upload.md`](14-user-upload.md:1) |
| 4 | Restricted / «пиратские» (последний fallback) | публичные mp3-каталоги, rutracker и подобные через прямую ссылку, Telegram-каналы с mp3-вложениями, mp3-агрегаторы | используются **только** если ничего из tier 1–3 не нашлось; помечаются `source_kind` с префиксом `restricted:` |

`source_kind` в `track_sources` отражает реальный домен/способ: `youtube`, `soundcloud`, `bandcamp`, `archive_org`, `fma`, `jamendo`, `user_upload`, `direct_url`, `restricted:<domain>`, `telegram`, и т.п. Источники tier 4 **никогда** не выбираются автоматически без явного действия пользователя (см. §«Загрузка кандидата»).

## Источники (технические адаптеры)

| Источник | Tier | Способ | Что берём |
|---|---|---|---|
| YouTube / YouTube Music | 2 | `yt-dlp` (`ytsearch10:<query>`) | bestaudio, title, channel, duration, thumbnail |
| SoundCloud | 1–2 (зависит от лицензии трека) | `yt-dlp` (`scsearch10:<query>`) | то же + `license` field |
| Bandcamp | 1–2 | `yt-dlp` по URL/`bcsearch` | bestaudio, обложка, теги |
| Free Music Archive | 1 | FMA API (`freemusicarchive.org/api`) | mp3 + CC-лицензия |
| Jamendo | 1 | Jamendo API (требует client_id, free tier) | mp3 + лицензия |
| archive.org | 1 | `yt-dlp` / прямой HTTP | aud-файлы, public domain / CC |
| Vimeo | 2 | `yt-dlp` | bestaudio (редко используется) |
| Прямая ссылка (`http(s)://.../*.mp3\|m4a\|flac\|opus\|ogg`) | 2–4 | httpx download | как есть |
| Restricted-агрегаторы (rutracker, mp3-сайты) | 4 | `yt-dlp` (когда поддерживается) + прямой HTTP | как есть, mp3 |
| Telegram-канал (опц., через user-bot) | 4 | TDLib / Pyrogram (отдельный воркер) | mp3-вложения, см. ниже |
| User upload | 3 | загрузка файла пользователем | mp3/m4a/flac/opus, см. [`14-user-upload.md`](14-user-upload.md:1) |

`yt-dlp` — единый абстрактный загрузчик для большинства источников tier 1–2 и части tier 4. Для FMA/Jamendo — отдельные HTTP-клиенты (более стабильный API). Telegram-адаптер — опциональное расширение, выключено по умолчанию (`TELEGRAM_SOURCE_ENABLED=false` в `.env`).

### Включение restricted-источников
- Глобально управляется `RESTRICTED_SOURCES_ENABLED=true|false` в `.env` (default: `true`, т.к. проект личный).
- На уровне пользователя — настройка `prefer_open_only` в профиле (default: `false`): если включено, search/resolver вообще не возвращает tier 4.
- В UI кандидат tier 4 помечается значком ⚠ и подсказкой «закрытый источник, может быть нестабилен».

## Поиск (как работает)

```
POST /search { query: "Linkin Park - Numb", limit: 10 }
```

1. Нормализация: trim, lower, collapse spaces.
2. `query_hash = sha256(normalized)`. Проверяем кеш `search_candidates` за последние 24 ч.
3. Если нет → параллельно опрашиваем адаптеры по tier-ам:
   - Tier 1: FMA, Jamendo, archive.org, SoundCloud (с фильтром по CC), Bandcamp.
   - Tier 2: YouTube/YouTube Music, SoundCloud (без фильтра), Vimeo.
   - Tier 4 (restricted): запускаются **только** если `RESTRICTED_SOURCES_ENABLED=true` и пользователь не включил `prefer_open_only`. Запросы идут с большим таймаутом и отдельным rate-limit.
4. Парсим ответы → формируем единый формат candidate с полями `tier`, `source_kind`, `license` (если известен).
5. Сохраняем в кеш `search_candidates`.
6. Сортируем: сначала по `tier` (1 → 2 → 4), потом по relevance score внутри tier. Tier 3 (`user_upload`) в /search не участвует — он проявляется только в локальном matcher-е.
7. Возвращаем top-N с указанием tier-а в ответе.

## Загрузка кандидата

```
POST /tracks/from-candidate { candidate_id }
```

1. Backend читает candidate из кеша.
2. Создаёт запись `Track(status=downloading, ...)` с базовыми полями.
3. Ставит задачу `download_track(track_id, candidate)` в RQ.
4. Возвращает `{track_id}`.

Воркер:
1. `yt-dlp --extract-audio --audio-format opus --audio-quality 96K -o /tmp/{tmp_id}.%(ext)s <url>`.
2. Считаем `audio_sha256` (хеш файла после транскода). Если такой уже есть → удаляем временный, ссылаемся на существующий Track, новый помечаем `merged_into=<id>` либо удаляем.
3. ffprobe → реальная длительность, битрейт.
4. Перемещаем файл в `storage/tracks/{id[:2]}/{id}.opus`.
5. Обновляем `Track.status='ready'`.
6. Ставим задачу `enrich_metadata`.

## Обогащение метаданных (`enrich_metadata`)

1. Парсим title в `artist - track` (если получается).
2. **MusicBrainz** (`musicbrainzngs` или прямой httpx, User-Agent обязателен):
   - Поиск recording по artist+title → mbid, album, isrc, year.
3. **Last.fm** (если ключ задан): теги/жанры по mbid или artist+title.
4. **Lyrics-проверка** (опц.): если есть текст — `has_lyrics=true`, иначе пометить `instrumental`. На MVP — по тегам/жанрам (genre in {ambient, classical, soundtrack, post-rock} → возможный инструментал).
5. Создаём/находим связанные `Artist`, `Album`, `Genre`. Связываем.
6. Сохраняем обложку: `albums.cover_path` (берём из MusicBrainz Cover Art Archive, fallback — thumbnail с YouTube).

## Аудио-фичи (`compute_audio_features`, опц.)

Через `librosa`:
- `bpm` (tempo).
- `energy` (rms среднее, нормализовано).
- `valence` — упрощённо: производная от mode (major/minor) + центроид спектра. На MVP можно опустить, использовать только теги/жанры.

Тяжёлая операция → выносится в low-priority queue.

## Дедупликация
- Уровень 1: `audio_sha256` (точный дубликат файла).
- Уровень 2: `mbid` (тот же recording).
- Уровень 3: artist+title fuzzy match (`pg_trgm` similarity > 0.9) — предупреждение, не блокировка.

## Хранение
- Контейнер: `opus` в `.opus` (96 kbps моно или стерео — определяет ffmpeg).
- Path: `STORAGE_LOCAL_PATH/tracks/{id[:2]}/{id}.opus`.
- Обложки: `STORAGE_LOCAL_PATH/covers/{album_id[:2]}/{album_id}.jpg` (max 1000×1000, jpeg q=85).

## Ошибки
- yt-dlp может вернуть ошибку: гео-блок, удалено, age-restricted → пишем в `tracks.status='failed'`, `metadata.error=<reason>`, событие в WS.
- Пользователь может повторить с другим кандидатом.

## Зависимости (бинарные)
- `ffmpeg` ≥ 6 (в Docker-образе backend).
- `yt-dlp` (pip-пакет, обновлять регулярно).
- Опц.: `fpcalc` (chromaprint) для AcoustID.

## Будущие улучшения
- AcoustID: точное распознавание уже скачанного → mbid.
- Свой fingerprinting на C++ (см. [`03-tech-stack.md`](03-tech-stack.md:1)).
- Кеширование популярных запросов в Redis с TTL.
