# 17. Импорт из внешних музыкальных сервисов

Цель: пользователь может перенести в Local Music свои треки и плейлисты из Spotify, Apple Music, Yandex Music и подобных. Поток — **двухэтапный**: сначала забираем у внешнего сервиса список треков и плейлистов (метаданные + ID), потом каждый трек прогоняется через стандартный пайплайн поиска и загрузки.

## 1. Общая идея

```
[External account] ─→ [Provider adapter] ─→ [ImportJob] ─→ [Track resolver] ─→ [Source matcher] ─→ [Downloader] ─→ [Library + Playlist]
```

1. Пользователь подключает аккаунт сервиса (через токен/учётные данные, либо загружает экспорт-файл — см. §3).
2. Adapter забирает список треков + плейлистов в едином внутреннем формате `ExternalTrack`/`ExternalPlaylist`.
3. Создаётся `ImportJob` со списком треков. Прогресс виден пользователю.
4. Для каждого `ExternalTrack` запускается **track resolver**:
   - Сначала ищем уже существующий локальный трек (по `isrc`, `mbid`, fuzzy artist+title+duration).
   - Если найден — используем его, в плейлист добавляем существующий.
   - Если нет — запускается тот же пайплайн, что в [`06-music-sourcing.md`](06-music-sourcing.md:1): поиск ведётся **по tier-ам** (открытые источники tier 1 → tier 2 → опц. tier 4), верификация (см. [`14-user-upload.md`](14-user-upload.md:1) §3 — source matching по матч-скору), загрузка top-1 кандидата автоматически. Правило выбора: лучший кандидат из tier 1 с `match ≥ 0.80`, иначе лучший из tier 2 с `match ≥ 0.85`, иначе (если `RESTRICTED_SOURCES_ENABLED` и `prefer_open_only=false`) tier 4 с `match ≥ 0.90`.
   - Если автоматического кандидата нет — попадает в «требует ручного выбора» (пользователь добавляет потом).
5. Параллельно создаётся локальный `Playlist` с тем же названием; в него добавляются все успешно разрешённые треки в исходном порядке.

## 2. Поддерживаемые провайдеры

| Провайдер | Способ доступа | Что забираем | Сложность |
|---|---|---|---|
| **Spotify** | Web API (OAuth2: scopes `user-library-read`, `playlist-read-private`) | saved tracks, playlists, артисты-следования | низкая |
| **Apple Music** | MusicKit (через Developer Token + user token) | playlists, library tracks | средняя (нужен Apple Developer + MusicKit JS/Swift) |
| **Yandex Music** | Неофициальный API (библиотека `yandex-music-api` на Python) — стабильность не гарантирована | избранное, плейлисты | средняя, риск отключения |
| **Файлы экспорта** | CSV/JSON, выгруженные пользователем (Last.fm, Soundiiz, TuneMyMusic экспорты) | то, что отдают сервисы | низкая, не требует OAuth |
| **YouTube Music** | yt-dlp / YouTube Data API (с пользовательской авторизацией) | плейлисты | средняя |

### Приоритет реализации (MVP импорта)
1. **CSV/JSON-импорт** (универсальный fallback для всех сервисов через сторонние конвертеры).
2. **Spotify** — самый чистый официальный API.
3. **Yandex Music** — неофициальный, но Python-библиотека хорошо поддерживается.
4. **Apple Music** — позже (требует Apple Developer Program и больше работы).

## 3. Способы аутентификации

### 3.1 OAuth2 (Spotify, Yandex Music если применимо)
- Backend выступает OAuth-клиентом.
- `GET /import/{provider}/connect` → редирект на провайдера → callback `GET /import/{provider}/callback?code=...`.
- Полученный `access_token` шифруется (AES-GCM, ключ из `APP_SECRET_KEY`) и хранится в новой таблице `external_accounts`.
- Refresh-токен обновляется автоматически.

### 3.2 Парольная авторизация (Yandex Music через неофициальный API)
- Пользователь вводит логин/пароль/`x-token` в форме.
- Не храним пароль; храним только `x-token` (зашифрованный).
- Предупреждение в UI: «неофициальный API, может перестать работать».

### 3.3 Импорт файла (без подключения аккаунта)
- Пользователь грузит CSV/JSON, экспортированный из:
  - Soundiiz, TuneMyMusic (объединяют все сервисы),
  - Spotify через privacy.spotify.com export,
  - Apple Music через `support.apple.com → Data and privacy → Request a copy`,
  - Yandex Music через сторонние утилиты типа `yandex-music-token` + парсер.
- Поддерживаемые форматы:
  - **CSV** колонки: `title, artist, album, isrc, duration_seconds, playlist`.
  - **JSON** массив с теми же полями.
  - Спец-формат **Soundiiz JSON** (см. их документацию) — парсится напрямую.
- Никакого взаимодействия с внешним сервисом не требуется.

> **Рекомендация:** на старте поддерживать только §3.3 (импорт файла). Это покрывает 90% сценариев и не требует OAuth-инфраструктуры. OAuth добавляется на следующих этапах.

## 4. Схема данных

### Новая таблица `external_accounts`
| Поле | Тип | Описание |
|---|---|---|
| id | uuid PK | |
| user_id | uuid FK users.id | |
| provider | text | `spotify, apple, yandex, youtube_music` |
| external_user_id | text | id пользователя в провайдере |
| access_token_enc | bytea | AES-GCM |
| refresh_token_enc | bytea null | |
| expires_at | timestamptz null | |
| created_at, updated_at | timestamptz | |
UNIQUE (user_id, provider)

### Новая таблица `import_jobs`
| Поле | Тип | Описание |
|---|---|---|
| id | uuid PK | |
| user_id | uuid FK users.id | |
| provider | text | + `file` для импорта файла |
| source_meta | jsonb | для `file`: имя файла, кол-во строк; для OAuth: snapshot ID |
| status | enum('queued','running','completed','failed','cancelled') | |
| total_tracks | int | |
| resolved_tracks | int | автоматически найдены |
| ambiguous_tracks | int | нужен ручной выбор |
| failed_tracks | int | |
| created_at, finished_at | timestamptz | |
| result_summary | jsonb | |

### Новая таблица `import_items`
| Поле | Тип | Описание |
|---|---|---|
| id | uuid PK | |
| job_id | uuid FK import_jobs.id ON DELETE CASCADE | |
| external_id | text null | id в провайдере |
| external_isrc | text null | |
| title | text not null | |
| artist | text not null | |
| album | text null | |
| duration_seconds | int null | |
| external_playlist_id | text null | |
| status | enum('pending','resolved','ambiguous','failed','skipped') | |
| matched_track_id | uuid FK tracks.id null | |
| candidates | jsonb default '[]' | для `ambiguous`: сохранённые кандидаты для UI |
| created_at | timestamptz | |

### Связь с плейлистами
Импортированный плейлист создаётся в обычной таблице `playlists` с пометкой `metadata.import = {provider, external_id, imported_at}`. При повторном импорте того же плейлиста — обновляется состав (поведение управляется параметром `mode`).

## 5. Алгоритм Track Resolver (детально)

```
def resolve(item: ExternalTrack) -> ResolveResult:
    # 1. Точный матч по ISRC
    if item.isrc:
        t = tracks.find_by_isrc(item.isrc)
        if t: return Resolved(t, source='local_isrc')

    # 2. Точный матч по mbid (если знаем)
    # 3. Fuzzy по artist+title+duration в локальной библиотеке
    candidates = tracks.fuzzy_search(item.artist, item.title, item.duration)
    if candidates and candidates[0].score > 0.92:
        return Resolved(candidates[0].track, source='local_fuzzy')

    # 4. Поиск в открытых источниках (см. 14-user-upload §3)
    external = source_matcher.search(f"{item.artist} - {item.title}", duration=item.duration)
    if external.top_score >= 0.85 and abs(external.top.duration - item.duration) <= 2:
        # автоматический даунлоад через стандартный пайплайн
        track = downloader.download_and_register(external.top, candidate_sources=external.candidates)
        return Resolved(track, source='auto_downloaded')

    if external.candidates:  # есть, но слабые
        return Ambiguous(candidates=external.candidates)

    return Failed(reason='no_candidates')
```

ImportJob проходится по всем item; результат — суммарная статистика.

## 6. Поведение при конфликтах и режимы

`POST /import/file` (или `/import/{provider}/start`) принимает параметры:

| Параметр | Значения | Описание |
|---|---|---|
| `mode` | `add` (по умолчанию), `replace` | для существующих локальных плейлистов с тем же именем |
| `auto_threshold` | float 0..1 (default 0.85) | при каком match-score докачивать автоматически |
| `create_missing` | bool (default true) | докачивать ли отсутствующие треки или только связывать существующие |
| `mark_unverified` | bool (default true) | помечать ли треки, добавленные через импорт, флагом `tracks.metadata.imported_from_external = true` |
| `playlists_filter` | string[] | имена/ID плейлистов для частичного импорта |

## 7. UI

Раздел «Импорт» в настройках:
- Карточки провайдеров: `Spotify (OAuth)`, `Yandex Music (OAuth/token)`, `Apple Music`, `Импорт из файла`.
- После запуска — прогресс-бар с разбивкой `resolved / ambiguous / failed`.
- По завершении — таблица `import_items` со статусами; для `ambiguous` строк есть кнопка «выбрать вручную» (показывает `candidates`, флоу как в обычном поиске).
- Для каждого плейлиста — ссылка на созданный локальный плейлист.

## 8. API

| Метод | Путь | Описание |
|---|---|---|
| GET  | `/import/providers` | список доступных провайдеров и их статусов (OAuth настроен / нет) |
| GET  | `/import/{provider}/connect` | начать OAuth-флоу |
| GET  | `/import/{provider}/callback` | callback от провайдера |
| DELETE | `/import/accounts/{provider}` | отвязать аккаунт |
| POST | `/import/file` | multipart: загрузить CSV/JSON; query params режима |
| POST | `/import/{provider}/start` | запустить импорт по подключённому OAuth-аккаунту |
| GET  | `/import/jobs` | список своих job'ов |
| GET  | `/import/jobs/{id}` | детали + статистика |
| GET  | `/import/jobs/{id}/items?status=ambiguous` | список item'ов с фильтром |
| POST | `/import/jobs/{id}/items/{item_id}/resolve` | вручную привязать item к локальному треку или к кандидату из `candidates` |
| POST | `/import/jobs/{id}/cancel` | отменить |

Все эндпоинты — под авторизацией пользователя; чужой job не виден.

## 9. Воркер

- Очередь `import:{job_id}` в RQ.
- Один worker обрабатывает item'ы последовательно, с rate-limit (например, не более 1 RPS к источникам), чтобы не нарваться на бан.
- Идемпотентность: если item уже `resolved` — пропуск.
- Возобновление: cancel → status='cancelled', при перезапуске можно создать новый job с тем же source_meta.

## 10. Зависимости и переменные окружения

```
# Spotify
SPOTIFY_CLIENT_ID=
SPOTIFY_CLIENT_SECRET=
SPOTIFY_REDIRECT_URI=https://music.example.com/api/v1/import/spotify/callback

# Yandex Music (неофициально)
YANDEX_MUSIC_TOKEN_ENC_KEY=  # если решим хранить долгоживущие x-token

# Apple Music
APPLE_MUSIC_TEAM_ID=
APPLE_MUSIC_KEY_ID=
APPLE_MUSIC_PRIVATE_KEY_PATH=/run/secrets/apple_music.p8
```

Python-зависимости:
- `spotipy` или ручная обёртка над Spotify Web API.
- `yandex-music` (PyPI).
- Для Apple Music — генерация JWT с ES256 на сервере, парсинг ответов вручную.

## 11. Безопасность

- Внешние токены **всегда** шифруются (AES-GCM, ключ — из `APP_SECRET_KEY`/отдельной secret).
- В UI токен не возвращается, только статус «подключён / отключён».
- Логи **не** содержат токены, OAuth-коды.
- При отключении аккаунта токены немедленно затираются.

## 12. Связь с другими документами
- Recreates источники через [`14-user-upload.md`](14-user-upload.md:1) §3 (source matching) — без дублирования логики.
- Расширяет [`04-database-schema.md`](04-database-schema.md:1) тремя таблицами (`external_accounts`, `import_jobs`, `import_items`).
- Расширяет [`05-api-spec.md`](05-api-spec.md:1) — раздел Import.
- Добавляется в [`12-roadmap.md`](12-roadmap.md:1) как **этап 4.3 «External imports»** (после Index & Restore).
- В [`11-security-legal.md`](11-security-legal.md:1) — пункт про шифрование внешних токенов.
- `track_sources` (см. [`16-library-index-and-restore.md`](16-library-index-and-restore.md:1)) пополняется при автоматическом скачивании во время импорта.

## 13. Что это даёт пользователю

1. Не нужно вручную переносить тысячи треков из Spotify/Yandex/Apple Music — за час сервис сам подтянет всё, что доступно публично.
2. История плейлистов сохраняется в исходном порядке.
3. Спорные треки попадают в очередь «выбрать вручную», а не теряются.
4. Все импортированные треки автоматически попадают в индекс (см. [`16-library-index-and-restore.md`](16-library-index-and-restore.md:1)) — переносимы дальше.
