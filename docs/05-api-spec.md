# 05. Спецификация REST API

Все эндпоинты под префиксом `/api/v1`. Авторизация — `Authorization: Bearer <access_token>` (JWT). Ошибки в формате RFC 7807 (`application/problem+json`):
```json
{ "type": "about:blank", "title": "Not Found", "status": 404, "detail": "Track not found", "trace_id": "..." }
```

> Полный контракт генерируется FastAPI автоматически и доступен в `/docs` (Swagger) и `/openapi.json`. Этот файл — высокоуровневый обзор.

## 1. Auth

| Метод | Путь | Описание |
|---|---|---|
| POST | `/auth/register` | Регистрация по invite-коду. Body: `{email, username, password, invite_code}`. |
| POST | `/auth/login` | Body: `{login, password}` → `{access_token, refresh_token, expires_in}`. |
| POST | `/auth/refresh` | Body: `{refresh_token}` → новые токены. |
| POST | `/auth/logout` | Invalidate refresh (опц.). |
| GET  | `/auth/me` | Профиль текущего пользователя. |
| PATCH| `/auth/me` | Обновить username, сменить пароль. |

## 2. Search & sourcing

| Метод | Путь | Описание |
|---|---|---|
| POST | `/search` | `{query: "...", limit: 10}` → список кандидатов. Кеш 24ч. |
| POST | `/tracks/from-candidate` | `{candidate_id}` → создаёт Track(status=downloading), ставит задачу в очередь. |
| GET  | `/tracks/{id}/status` | Статус загрузки/обработки. |
| WS   | `/ws/tracks` | События: `track.status_changed`, `track.ready`, `track.failed`. |
| POST | `/tracks/upload` | Ручная загрузка файла (multipart). См. [`14-user-upload.md`](14-user-upload.md:1). |
| GET  | `/tracks/upload/{upload_id}/verify` | Запуск/получение результата верификации. |
| POST | `/tracks/upload/{upload_id}/confirm` | Подтверждение публикации в библиотеку. |

Структура candidate:
```json
{
  "candidate_id": "c_abc123",
  "title": "Numb",
  "artist": "Linkin Park",
  "duration": 187,
  "thumbnail_url": "...",
  "source_kind": "youtube",
  "source_id": "kXYiU_JCYtU"
}
```

## 3. Tracks

| Метод | Путь | Описание |
|---|---|---|
| GET  | `/tracks` | Каталог. Query: `q, artist, genre, language, year_from, year_to, has_lyrics, sort, page, page_size`. |
| GET  | `/tracks/{id}` | Полная инфа: artists, album, genres, languages, audio features. |
| GET  | `/tracks/{id}/stream` | Стрим аудио. Поддержка `Range`. |
| POST | `/tracks/{id}/play` | Логирование начала прослушивания → `{play_id}`. |
| POST | `/plays/{play_id}/heartbeat` | `{listened_seconds, completed}` — раз в N сек. |
| DELETE | `/tracks/{id}` | Только admin. |

## 4. Likes

| Метод | Путь | Описание |
|---|---|---|
| PUT  | `/tracks/{id}/like` | sentiment: `like`/`dislike`. like также добавит в «Любимое». |
| DELETE | `/tracks/{id}/like` | Снять реакцию. |

## 5. Playlists

| Метод | Путь | Описание |
|---|---|---|
| GET  | `/playlists` | Мои + публичные. |
| POST | `/playlists` | `{name, is_public}`. |
| GET  | `/playlists/{id}` | Содержимое. |
| PATCH| `/playlists/{id}` | Переименовать / изменить публичность / обложку. |
| DELETE | `/playlists/{id}` | Удалить (нельзя для is_favourite). |
| POST | `/playlists/{id}/tracks` | `{track_ids: [...]}` добавить. |
| DELETE | `/playlists/{id}/tracks/{track_id}` | Удалить. |
| POST | `/playlists/{id}/reorder` | `{track_ids: [...]}` — новый порядок. |

## 6. Vibe (моя волна)

| Метод | Путь | Описание |
|---|---|---|
| POST | `/vibe/session` | Создать сессию. Body: `{mood, genres, languages, mode}`. Возвращает `{session_id, queue: [track,...]}`. |
| POST | `/vibe/{session_id}/next` | Вернуть следующий батч (по 5 треков). |
| POST | `/vibe/{session_id}/feedback` | `{track_id, action: "like"\|"dislike"\|"skip"\|"played"}`. |
| GET  | `/vibe/presets` | Список заранее сохранённых пресетов пользователя. |
| POST | `/vibe/presets` | Сохранить пресет. |

Подробности — [`07-vibe-recommendations.md`](07-vibe-recommendations.md:1).

## 7. Reference data

| GET | `/genres` | Список жанров. |
| GET | `/languages` | Список языков. |
| GET | `/artists?q=...` | Поиск по исполнителям (autocomplete). |

## 8. Admin / Master

Подробные правила доступа — [`15-master-account.md`](15-master-account.md:1).

| Метод | Путь | Кто | Описание |
|---|---|---|---|
| GET    | `/admin/users` | admin / master | Список. |
| POST   | `/admin/users` | master | Создать пользователя без invite. |
| PATCH  | `/admin/users/{id}` | admin / master | Ban/unban, базовые поля. `is_master` всегда игнорируется. |
| PATCH  | `/admin/users/{id}/role` | **master** | Назначить/снять `admin`. |
| DELETE | `/admin/users/{id}` | master | Удалить (master удалить нельзя — 403). |
| POST   | `/admin/invites` | admin / master | Создать invite. |
| GET    | `/admin/audit-log` | master | Полный аудит-лог. |
| GET    | `/admin/stats` | admin / master | Статистика. |
| POST   | `/admin/index/export` | master | Запустить экспорт library index (async). Параметры: `include_covers, include_secrets, no_plays, minimal`. |
| GET    | `/admin/index/exports` | master | Список доступных дампов. |
| GET    | `/admin/index/exports/{file}` | master | Скачать дамп. |
| POST   | `/admin/index/import` | master | Импорт дампа. Параметры: `mode=skip-existing\|overwrite\|mirror`. |
| POST   | `/admin/library/restore` | master | Запустить пересборку аудио по `track_sources`. Параметры: `strategy, concurrency, dry_run`. |
| GET    | `/admin/library/health` | admin / master | Сводка: `missing_files`, `unrecoverable`, источники по статусам. |

Подробности — [`16-library-index-and-restore.md`](16-library-index-and-restore.md:1).

## 9. Shazam (опц.)

| POST | `/shazam/recognize` | multipart audio fragment (5-10 сек) → `{title, artist, ...}` или `null`. |

Подробности — [`08-shazam-integration.md`](08-shazam-integration.md:1).

## 10. Import (внешние сервисы)

Полная спецификация — [`17-external-imports.md`](17-external-imports.md:1).

| Метод | Путь | Описание |
|---|---|---|
| GET    | `/import/providers` | Список доступных провайдеров и их статус для текущего пользователя. |
| POST   | `/import/connect/{provider}` | Старт OAuth-флоу (`spotify`, `apple_music`, `youtube_music`). Возвращает `authorize_url`. |
| GET    | `/import/callback/{provider}` | OAuth callback. Сохраняет зашифрованные токены в `external_accounts`. |
| POST   | `/import/connect/yandex` | Body: `{token}` — сохранить токен Яндекс.Музыки вручную. |
| DELETE | `/import/accounts/{provider}` | Отвязать внешний аккаунт. |
| POST   | `/import/file` | multipart `file` (CSV/JSON) + `params` → создаёт `import_job`. |
| POST   | `/import/{provider}/liked` | Импорт «лайков» из подключённого внешнего сервиса. |
| POST   | `/import/{provider}/playlists` | Body: `{playlist_ids: [...]}` или `all: true`. |
| GET    | `/import/jobs` | Список заданий пользователя, фильтр по `status`. |
| GET    | `/import/jobs/{id}` | Подробности задания + `stats`. |
| POST   | `/import/jobs/{id}/cancel` | Отменить задание. |
| GET    | `/import/jobs/{id}/items` | Позиции импорта, фильтр `?status=ambiguous\|failed\|...`. |
| POST   | `/import/items/{id}/resolve` | Ручной выбор кандидата для `ambiguous`. Body: `{candidate_id}` или `{track_id}` или `{skip: true}`. |
| WS     | `/ws/import` | События прогресса: `import.job.progress`, `import.job.completed`, `import.item.ambiguous`. |

## 11. Rate limits
- `/auth/login`: 5/min/IP.
- `/auth/register`: 3/hour/IP.
- `/search`: 30/min/user.
- `/tracks/from-candidate`: 20/hour/user.
- `/import/*` запуск заданий: 10/hour/user (для предотвращения злоупотреблений внешними API).

## 12. Pagination
- Cursor-based для каталога: `?cursor=...&limit=50` (рекомендуется).
- Offset/limit допустим для админских списков.
- Все списки возвращают `{ items, next_cursor, total? }`.

## 13. Версионирование
- Major version в URL (`/v1`).
- Breaking changes → `/v2` + период двойной поддержки.
