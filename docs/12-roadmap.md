# 12. Roadmap

План разбит на этапы. У каждого этапа — Definition of Done (DoD). Этап считается закрытым только после выполнения всех чек-листов.

Легенда: `[ ]` pending, `[-]` in progress, `[x]` done.

---

## Этап 0. Подготовка и документация ✅
- [x] Создать репозиторий и базовую структуру.
- [x] Заполнить `docs/`.
- [x] Создать GitHub-репозиторий и сделать первый push (см. [`13-development-guide.md`](13-development-guide.md:1)). Репозиторий: https://github.com/makoevvv/local_music
- [ ] Установить инструменты на сервере (Docker Desktop, brew, git, ffmpeg).

**DoD:** документация в `docs/` отражает MVP, репозиторий на GitHub, у владельца есть локальный clone.

---

## Этап 1. Скелет backend + Docker ✅
- [x] Создать структуру `backend/` (см. [`02-architecture.md`](02-architecture.md:1) §2.1).
- [x] `pyproject.toml`, `ruff`, `black`, `mypy`, `pytest`.
- [x] `app/main.py` — FastAPI с health-check.
- [x] `app/core/config.py` через pydantic-settings.
- [x] Подключение к Postgres + Redis (async).
- [x] Alembic init + первая миграция (users).
- [x] `infra/docker-compose.yml`: postgres, redis, backend.
- [x] `Dockerfile` для backend.
- [x] CI: pytest + ruff + mypy в GitHub Actions.

**DoD:** `docker compose up` → `curl http://localhost:8000/health` отдаёт `200 {status: "ok"}`. Тесты в CI зелёные.

---

## Этап 2. Auth + master-аккаунт + базовые модели ✅
- [x] Модели: User (с `is_master`), Invite.
- [x] Миграции + триггеры запрета удаления/изменения master (см. [`15-master-account.md`](15-master-account.md:1)).
- [x] Регистрация (invite) / логин / refresh / me.
- [x] argon2 для паролей, JWT.
- [x] Middleware авторизации, `require_admin`, `require_master`.
- [x] CLI: `init-master` (одноразовый), `create-invite`, `reset-master-password`.
- [x] Эндпоинты `/admin/users/*` и `/admin/users/{id}/role` (только master).
- [x] Тесты: попытка удалить master → 403, попытка изменить `is_master` → 403, единственность master в БД.

**DoD:** master создан через CLI, по curl авторизован; обычный пользователь регистрируется по invite; admin/master эндпоинты возвращают корректные коды.

---

## Этап 3. Каталог + плейлисты + плеер (web MVP) ✅
- [x] Модели: Artist, Album, Genre, Language, Track, Playlist, PlaylistTrack, Play, Like.
- [x] Миграции + seed (genres, languages).
- [x] CRUD плейлистов; автосоздание «Любимое».
- [x] Эндпоинты каталога с фильтрами.
- [x] Endpoint стриминга с Range.
- [x] Скелет web (`web/`): Vite + React + TS + Tailwind + Router.
- [x] Страницы: Login, Catalog, Track page, Playlists, Playlist detail.
- [x] Плеер (HTML5 audio + UI), очередь, прогресс.
- [x] Лайки, добавление в плейлист.

**DoD:** в браузере можно залогиниться, увидеть каталог (можно тестовыми треками, загруженными вручную), послушать, добавить в плейлист.

---

## Этап 4. Поиск и загрузка из интернета ✅
- [x] yt-dlp + ffmpeg в Docker-образе backend.
- [x] Эндпоинт `/search` с кешем (Redis + `search_candidates`).
- [x] Эндпоинт `/tracks/from-candidate`, `/tracks/{id}/status`.
- [x] RQ-воркер: `download_track`, дедупликация по `audio_sha256`.
- [x] Обогащение метаданных: MusicBrainz (то же разрешение альбома, что в этапе 4.1), Last.fm (best-effort, не блокирует `ready`).
- [x] WebSocket уведомления о статусе (`/api/v1/ws/tracks`).
- [x] Web UI: Search, выбор кандидата, прогресс.
- [x] Инфра: сервис `ytdlp-pot` (PO Token, без cookies браузера); опционально VPN — профиль `proxy` + `YTDLP_PROXY` (см. [`infra/proxy/README.md`](../infra/proxy/README.md)).

**DoD:** пользователь ввёл запрос → выбрал → через ~30 сек трек слушается; жанр/альбом — по возможности из MusicBrainz/Last.fm.

> **Индекс библиотеки (`track_sources`, export/import):** на этом этапе **не делаем** — только поля `tracks.source_*`. Полноценный индекс — этап 4.2.

---

## Этап 4.1. Ручная загрузка треков и верификация ✅
Подробности — [`14-user-upload.md`](14-user-upload.md:1).
- [x] Эндпоинты `/tracks/upload`, `/tracks/upload/{id}/verify`, `/tracks/upload/{id}/confirm`.
- [x] Парсер встроенных тегов (`mutagen`).
- [x] Бинарь `fpcalc` (chromaprint) в образе backend; интеграция с AcoustID API.
- [x] Верификатор: AcoustID → MusicBrainz fuzzy → эвристики; уровни trust `high/medium/low/none`.
- [x] Album resolution: по mbid recording'а из AcoustID → MusicBrainz `release-group.primary-type` → реальный альбом или подтверждённый сингл (см. [`14-user-upload.md`](14-user-upload.md:1) §2).
- [x] Фоновый воркер `reconcile_albums` (раз в сутки) — повторное разрешение для треков с `metadata.album_unresolved=true`.
- [x] `is_single=true` ставится только при подтверждённом primary-type=Single.
- [x] RQ-воркер `cleanup_uploads` (TTL 30 минут).
- [x] **Source matching**: после загрузки backend ищет тот же трек в открытых источниках (yt-dlp ytsearch/scsearch), показывает кандидатов в карточке верификации (см. [`14-user-upload.md`](14-user-upload.md:1) §3).
- [x] Запись всех подтверждённых кандидатов в `track_sources` с правильным `recovery_priority` (публичные < `user_upload`).
- [x] Фоновый воркер `match_user_uploads` (раз в сутки) — повторный поиск публичных источников для треков, у которых только `user_upload`.
- [x] UI: вкладка «Загрузить файл», карточка верификации с предложениями метаданных и списком найденных источников; выбор primary.

**DoD:** пользователь загружает локальный mp3 → видит распознанные метаданные **и** список найденных публичных кандидатов (если есть) → подтверждает с выбором primary-источника → трек появляется в библиотеке, в индексе есть и `user_upload`, и публичные ссылки.

> Кнопка «promote» (заменить файл пользователя публичным) — этап 7. iOS document picker — этап 6. ShazamKit на устройстве не входит в backend.

---

## Этап 4.2. Index & Restore (переносимая библиотека) ✅
Подробности — [`16-library-index-and-restore.md`](16-library-index-and-restore.md:1).
- [x] Миграция: таблица `track_sources`, поле `tracks.acoustid_fingerprint`, статус `unrecoverable`.
- [x] При создании трека (download из search, CLI `import-track`) **всегда** пишем запись в `track_sources` (+ backfill в миграции).
- [x] CLI: `index export` (jsonl + manifest, `--minimal/--include-covers/--include-secrets/--no-plays`).
- [x] CLI: `index import --mode=skip-existing|overwrite|mirror` с обработкой конфликтов UUID/sha256.
- [x] CLI: `library restore` (yt-dlp по `track_sources`, fuzzy fallback по artist/title; AcoustID API — этап 4.1).
- [x] Воркер/CLI `verify-sources` (лёгкая проверка доступности ссылок).
- [x] Admin/Master эндпоинты `/admin/index/*` и `/admin/library/*`.
- [x] Расписание: `infra/scripts/export_index.sh` (ежедневный minimal + еженедельный full).
- [x] JSON-схема [`docs/schemas/library.schema.json`](schemas/library.schema.json).

**DoD:** на чистом сервере по тарболу `library-*.tar.gz` можно восстановить структуру библиотеки (метаданные) и перекачать аудио для треков с живыми источниками; статистика по «протухшим» источникам видна master'у.

---

## Этап 4.3. External imports (Spotify / Yandex / Apple Music / file) ✅
Подробности — [`17-external-imports.md`](17-external-imports.md:1).
- [x] Миграция: таблицы `external_accounts`, `import_jobs`, `import_items`, поле `playlists.metadata`.
- [x] Универсальный парсер CSV/JSON (колонки title/artist/album/isrc/duration/playlist и JSON плейлистов).
- [x] Spotify OAuth-адаптер (ручной HTTP-клиент): authorize URL, callback, liked tracks + playlists.
- [x] Yandex Music adapter: пользовательский токен, лайки через неофициальный API.
- [ ] (опц.) Apple Music через MusicKit + Developer JWT ES256.
- [x] Track resolver: ISRC → локальный fuzzy → авто-загрузка (`match ≥ auto_threshold`, по умолчанию 0.85) → `ambiguous`.
- [x] RQ-воркер `process_import_job` с паузой между поисками вне тестового окружения.
- [x] API `/import/*` (providers, connect, callback, file, jobs, items, resolve, cancel).
- [x] UI «Импорт»: загрузка файла, прогресс, очередь ambiguous с выбором кандидата.
- [x] Шифрование внешних токенов AES-GCM (`EXTERNAL_TOKENS_KEY` или SHA-256 от `APP_SECRET_KEY`).
- [x] Идемпотентность: повтор того же файла в том же режиме возвращает существующий job.

**DoD:** пользователь загружает CSV из Spotify-экспорта (или подключает OAuth) → создаются соответствующие плейлисты, треки автоматически скачиваются при уверенном матче, неразрешённые — попадают в очередь «ambiguous» для ручного выбора; повтор импорта идемпотентен.

---

## Этап 5. «Моя волна» ✅
- [x] mood_profiles, scorer, pool, session, feedback.
- [x] Эндпоинты `/vibe/*`.
- [x] UI главной страницы с настройками волны.
- [x] Кнопки like/dislike/skip влияют на следующий батч.
- [x] User-affinity счётчики в Redis + снимок в БД.

Эмбеддинги / pgvector, коллаборативная фильтрация, время суток и A/B пресетов остаются в «Будущем» документа [`07-vibe-recommendations.md`](07-vibe-recommendations.md:1). Apple Music по-прежнему опциональный пункт этапа 4.3.

**DoD:** на главной можно включить волну, слушать ≥ 30 минут, реакции влияют на подбор (проверяется субъективно).

---

## Этап 6. iOS-приложение (базовое)
- [x] Xcode-проект в `ios/`.
- [x] Login + Keychain.
- [x] APIClient (async/await).
- [x] Catalog, Player (AVPlayer), Playlists.
- [x] Background audio + Now Playing.
- [ ] Установка на личный iPhone через Xcode.
- [ ] (Опц.) TestFlight upload.

**DoD:** приложение собирается, ставится на iPhone владельца, можно слушать музыку из домашнего сервера.

---

## Этап 7. Полировка и стабилизация
- [x] Cloudflare Tunnel: сервис `cloudflared` в профиле `edge`, токен в `CLOUDFLARE_TUNNEL_TOKEN` (логин в Cloudflare — у владельца).
- [x] HTTPS + Caddy в продакшн-варианте (`infra/Caddyfile`, профиль `edge`).
- [x] Бэкапы по расписанию (`infra/scripts/backup_db.sh`, cron и launchd).
- [x] Мониторинг (Uptime Kuma), профиль compose `monitor`, UI на `127.0.0.1:3001`.
- [x] Логи структурированы (JSON), уровень через `LOG_LEVEL`.
- [ ] Покрытие тестами критичных модулей ≥ 60%.
- [ ] README обновлён, инструкция «как поднять» проверена с нуля.

**DoD:** сервис работает 7 дней без перезапуска, доступен извне с iPhone, бэкапы появляются ежедневно.

---

## Этап 8 (опц.). Расширения
- [ ] AcoustID/Chromaprint для распознавания.
- [ ] ShazamKit в iOS.
- [ ] Android-клиент.
- [ ] Audio features через librosa.
- [ ] C++-микросервис для тяжёлой обработки (если захочется).
- [ ] Социальные плейлисты, общие очереди.

---

## Принципы работы по этапам
1. Никогда не начинать новый этап, пока предыдущий не закрыт по DoD.
2. После закрытия этапа — обновить статус здесь и в README.
3. Все нестандартные решения внутри этапа — в ADR (`docs/adr/`).
4. Каждый этап = ветка `stage/N-...`, мерж через PR.
