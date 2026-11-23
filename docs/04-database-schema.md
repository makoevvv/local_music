# 04. Схема базы данных

PostgreSQL 16. Все таблицы — `snake_case`. PK — `UUID` (`uuid_generate_v4()` или `gen_random_uuid()`).

## ER-диаграмма (текстом)

```
users ───< playlists ───< playlist_tracks >─── tracks >─── track_artists >─── artists
  │                                              │              │
  │                                              ├─< plays      ├─< track_genres >─── genres
  │                                              ├─< likes      └─── album ─── albums
  └─< invites                                    └─< track_languages >─── languages
```

## Таблицы

### `users`
| Поле | Тип | Описание |
|---|---|---|
| id | uuid PK | |
| email | text unique not null | |
| username | text unique not null | |
| password_hash | text not null | argon2 |
| role | enum('admin','user') default 'user' | |
| is_master | bool not null default false | владелец сервиса; см. [`15-master-account.md`](15-master-account.md:1) |
| is_active | bool default true | |
| created_at | timestamptz default now() | |
| updated_at | timestamptz | |

Дополнительно — partial unique index, гарантирующий, что мастер только один:
```sql
CREATE UNIQUE INDEX users_single_master_idx ON users ((1)) WHERE is_master = true;
```
Триггеры запрета удаления и изменения `is_master` описаны в [`15-master-account.md`](15-master-account.md:1).

> **Этап 2:** миграция `20260528_0002` добавляет `users.is_master`, таблицы `invites`, `refresh_tokens`, `audit_log` и триггеры защиты master (см. [`15-master-account.md`](15-master-account.md:1)).

### `invites`
| id | uuid PK |
| code | text unique not null |
| used_by_user_id | uuid FK users.id null |
| created_by_user_id | uuid FK users.id |
| expires_at | timestamptz null |
| created_at | timestamptz |

### `artists`
| id | uuid PK |
| name | text not null |
| mbid | text unique null | MusicBrainz ID |
| sort_name | text |
| metadata | jsonb default '{}' | теги, ссылки, страна |
| created_at | timestamptz |

### `albums`
| id | uuid PK |
| title | text not null |
| primary_artist_id | uuid FK artists.id |
| mbid | text unique null |
| release_year | int null |
| cover_path | text null |
| is_single | bool default false | сингл-альбом, созданный автоматически при ручной загрузке трека без альбома |
| metadata | jsonb default '{}' |

### `genres`
| id | uuid PK |
| name | text unique not null |
| slug | text unique not null |

### `languages`
| id | uuid PK |
| code | text unique not null | ISO 639-1, плюс спец-код `inst` для instrumental |
| name | text not null |

### `tracks`
| id | uuid PK |
| title | text not null |
| album_id | uuid FK albums.id null |
| duration_seconds | int |
| file_path | text not null | путь в storage |
| file_format | text | `opus`, `m4a`, `mp3` |
| file_size_bytes | bigint |
| audio_sha256 | text unique | для дедупликации |
| source_kind | text | `youtube`, `soundcloud`, `bandcamp`, `upload`, ... |
| source_url | text null |
| source_id | text null | id внутри источника |
| mbid | text unique null |
| isrc | text null |
| explicit | bool default false |
| has_lyrics | bool default true | для фильтра «без слов» |
| bpm | float null |
| energy | float null | 0..1 |
| valence | float null | 0..1 (грусть/радость) |
| status | enum('downloading','ready','failed','blocked') default 'downloading' |
| added_by_user_id | uuid FK users.id |
| play_count | int default 0 | денормализованное |
| acoustid_fingerprint | text null | chromaprint fingerprint для восстановления |
| cover_url_origin | text null | URL источника обложки |
| created_at | timestamptz |
| updated_at | timestamptz |

Индексы:
- `idx_tracks_title_trgm` GIN (`title` gin_trgm_ops)
- `idx_tracks_status` btree (`status`)
- `idx_tracks_created_at` btree (`created_at desc`)

### `track_artists`
| track_id | uuid FK tracks.id |
| artist_id | uuid FK artists.id |
| role | enum('main','feat','remixer') default 'main' |
| position | int default 0 |
PK: (track_id, artist_id, role)

### `track_genres`
| track_id | uuid FK tracks.id |
| genre_id | uuid FK genres.id |
| weight | float default 1.0 |
PK: (track_id, genre_id)

### `track_languages`
| track_id | uuid FK tracks.id |
| language_id | uuid FK languages.id |
PK: (track_id, language_id)

### `track_sources`
История источников трека — основа для восстановления библиотеки. См. [`16-library-index-and-restore.md`](16-library-index-and-restore.md:1).

| Поле | Тип | Описание |
|---|---|---|
| id | uuid PK | |
| track_id | uuid FK tracks.id ON DELETE CASCADE | |
| source_kind | text not null | `youtube`, `soundcloud`, `bandcamp`, `direct_url`, `user_upload`, `unknown` |
| source_url | text null | |
| source_id | text null | id внутри источника |
| original_filename | text null | для `user_upload` |
| original_tags | jsonb default '{}' | сырые ID3-теги |
| added_by_user_id | uuid FK users.id | |
| added_at | timestamptz default now() | |
| recovery_priority | int default 100 | меньше → выше приоритет при восстановлении |
| last_checked_at | timestamptz null | |
| last_status | text null | `ok`, `gone`, `geo_blocked`, `private`, `forbidden`, `checksum_mismatch` |

Индексы:
- `idx_track_sources_track` (`track_id`).
- `idx_track_sources_kind_status` (`source_kind`, `last_status`).

> **Статус реализации:** таблица `track_sources` — этап **4.2** (ещё нет в миграциях). На этапе **4** при скачивании из search заполняются только denormalized поля `tracks.source_kind`, `tracks.source_id`, `tracks.source_url`, `tracks.cover_url_origin`. После 4.2 — дублируем/нормализуем в `track_sources` и backfill для существующих треков.

### `playlists`
| id | uuid PK |
| owner_id | uuid FK users.id |
| name | text not null |
| is_favourite | bool default false | признак «Любимое», уникален на пользователя |
| is_public | bool default false |
| cover_path | text null |
| created_at, updated_at | timestamptz |

Constraint: `UNIQUE (owner_id) WHERE is_favourite = true`.

### `playlist_tracks`
| playlist_id | uuid FK playlists.id |
| track_id | uuid FK tracks.id |
| position | int |
| added_at | timestamptz |
PK: (playlist_id, track_id)

### `plays`
| id | bigserial PK |
| user_id | uuid FK users.id |
| track_id | uuid FK tracks.id |
| started_at | timestamptz |
| listened_seconds | int |
| completed | bool default false | прослушано >50% |
| source | text | `library`, `vibe`, `playlist:<id>` |

Индексы:
- `idx_plays_user_started` (`user_id`, `started_at desc`)
- `idx_plays_track` (`track_id`)

### `likes`
| user_id | uuid FK users.id |
| track_id | uuid FK tracks.id |
| created_at | timestamptz |
| sentiment | enum('like','dislike') |
PK: (user_id, track_id)

### `search_candidates` (кеш результатов поиска)
| id | uuid PK |
| query_hash | text | sha256(query.lower().strip()) |
| source_kind | text |
| source_id | text |
| payload | jsonb | сырой ответ источника |
| created_at | timestamptz |

Индекс: `idx_search_query_hash`.

### `external_accounts` (привязка внешних сервисов для импорта)
| Поле | Тип | Описание |
|---|---|---|
| id | uuid PK | |
| user_id | uuid FK users.id not null | владелец привязки |
| provider | text not null | `spotify`, `yandex_music`, `apple_music`, `youtube_music` |
| external_user_id | text null | id во внешней системе (если доступен) |
| access_token_enc | bytea null | AES-GCM(ciphertext) |
| refresh_token_enc | bytea null | AES-GCM(ciphertext) |
| token_nonce | bytea null | nonce для AES-GCM |
| token_expires_at | timestamptz null | |
| scope | text null | OAuth scope |
| status | enum('active','expired','revoked') default 'active' | |
| created_at | timestamptz default now() | |
| updated_at | timestamptz | |

Уникальный индекс: `(user_id, provider)`. Подробности — [`17-external-imports.md`](17-external-imports.md:1).

### `import_jobs` (задания на импорт)
| Поле | Тип | Описание |
|---|---|---|
| id | uuid PK | |
| user_id | uuid FK users.id not null | |
| provider | text not null | `spotify` / `yandex_music` / `apple_music` / `youtube_music` / `file` |
| source_kind | text not null | `liked`, `playlist`, `library`, `csv`, `json` |
| source_ref | text null | id плейлиста, имя файла и т.п. |
| params | jsonb default '{}' | настройки (auto_download_threshold, create_playlist, ...) |
| status | enum('queued','running','partial','completed','failed','cancelled') default 'queued' | |
| stats | jsonb default '{}' | `{total, resolved, downloaded, ambiguous, failed}` |
| error | text null | |
| created_at | timestamptz default now() | |
| started_at | timestamptz null | |
| finished_at | timestamptz null | |

Индексы: `(user_id, created_at desc)`, `(status)`.

### `import_items` (позиция импорта = одна внешняя ссылка на трек)
| Поле | Тип | Описание |
|---|---|---|
| id | uuid PK | |
| job_id | uuid FK import_jobs.id not null on delete cascade | |
| external_id | text null | id трека во внешней системе |
| isrc | text null | если есть |
| title | text not null | |
| artist | text not null | |
| album | text null | |
| duration_ms | int null | |
| raw | jsonb default '{}' | сырые поля источника |
| status | enum('pending','resolved','downloaded','ambiguous','failed','skipped') default 'pending' | |
| match_score | numeric(4,3) null | финальный score резолвера |
| resolved_track_id | uuid FK tracks.id null | |
| candidates | jsonb default '[]' | топ-N кандидатов для ambiguous |
| error | text null | |
| created_at | timestamptz default now() | |
| updated_at | timestamptz | |

Индексы: `(job_id, status)`, `(isrc)`. Для идемпотентности: уникальный частичный индекс `(job_id, external_id)` при `external_id is not null`.

### `refresh_tokens`
| Поле | Тип | Описание |
|---|---|---|
| id | uuid PK | |
| user_id | uuid FK users.id ON DELETE CASCADE | |
| token_hash | text unique not null | sha256 от refresh-токена |
| expires_at | timestamptz not null | |
| revoked_at | timestamptz null | |
| created_at | timestamptz default now() | |

### `audit_log` (минимальный аудит admin-действий)
| id | bigserial PK |
| actor_id | uuid FK users.id |
| action | text |
| target_kind | text |
| target_id | text |
| metadata | jsonb |
| created_at | timestamptz |

## Миграции
- Управляются Alembic. Каждая миграция = 1 PR.
- Имя файла: `{YYYYMMDD_HHMM}_{slug}.py`.
- В CI прогон `alembic upgrade head` на чистой БД.

## Стартовые данные (seed)
- Языки (ISO 639-1 + `inst`).
- Базовый список жанров (rock, pop, hip-hop, electronic, classical, jazz, metal, ambient, folk, soundtrack, ...).
- Master-аккаунт создаётся CLI-командой `python -m app.cli init-master` (один раз). Подробности — [`15-master-account.md`](15-master-account.md:1).
