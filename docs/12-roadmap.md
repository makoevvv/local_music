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

## Этап 2. Auth + master-аккаунт + базовые модели
- [ ] Модели: User (с `is_master`), Invite.
- [ ] Миграции + триггеры запрета удаления/изменения master (см. [`15-master-account.md`](15-master-account.md:1)).
- [ ] Регистрация (invite) / логин / refresh / me.
- [ ] argon2 для паролей, JWT.
- [ ] Middleware авторизации, `require_admin`, `require_master`.
- [ ] CLI: `init-master` (одноразовый), `create-invite`, `reset-master-password`.
- [ ] Эндпоинты `/admin/users/*` и `/admin/users/{id}/role` (только master).
- [ ] Тесты: попытка удалить master → 403, попытка изменить `is_master` → 403, единственность master в БД.

**DoD:** master создан через CLI, по curl авторизован; обычный пользователь регистрируется по invite; admin/master эндпоинты возвращают корректные коды.

---

## Этап 3. Каталог + плейлисты + плеер (web MVP)
- [ ] Модели: Artist, Album, Genre, Language, Track, Playlist, PlaylistTrack, Play, Like.
- [ ] Миграции + seed (genres, languages).
- [ ] CRUD плейлистов; автосоздание «Любимое».
- [ ] Эндпоинты каталога с фильтрами.
- [ ] Endpoint стриминга с Range.
- [ ] Скелет web (`web/`): Vite + React + TS + Tailwind + Router.
- [ ] Страницы: Login, Catalog, Track page, Playlists, Playlist detail.
- [ ] Плеер (HTML5 audio + UI), очередь, прогресс.
- [ ] Лайки, добавление в плейлист.

**DoD:** в браузере можно залогиниться, увидеть каталог (можно тестовыми треками, загруженными вручную), послушать, добавить в плейлист.

---

## Этап 4. Поиск и загрузка из интернета
- [ ] yt-dlp в Docker-образе backend.
- [ ] Эндпоинт `/search` с кешем (Redis + `search_candidates`).
- [ ] Эндпоинт `/tracks/from-candidate`.
- [ ] RQ-воркер: `download_track`, дедупликация по `audio_sha256`.
- [ ] Обогащение метаданных: MusicBrainz, Last.fm.
- [ ] WebSocket уведомления о статусе.
- [ ] UI: поиск, выбор кандидата, прогресс.

**DoD:** пользователь ввёл запрос → выбрал → через ~30 сек трек слушается, есть обложка и жанр.

---

## Этап 4.1. Ручная загрузка треков и верификация
Подробности — [`14-user-upload.md`](14-user-upload.md:1).
- [ ] Эндпоинты `/tracks/upload`, `/tracks/upload/{id}/verify`, `/tracks/upload/{id}/confirm`.
- [ ] Парсер встроенных тегов (`mutagen`).
- [ ] Бинарь `fpcalc` (chromaprint) в образе backend; интеграция с AcoustID API.
- [ ] Верификатор: AcoustID → MusicBrainz fuzzy → эвристики; уровни trust `high/medium/low/none`.
- [ ] Album resolution: по mbid recording'а из AcoustID → MusicBrainz `release-group.primary-type` → реальный альбом или подтверждённый сингл (см. [`14-user-upload.md`](14-user-upload.md:1) §2).
- [ ] Фоновый воркер `reconcile_albums` (раз в сутки) — повторное разрешение для треков с `metadata.album_unresolved=true`.
- [ ] `is_single=true` ставится только при подтверждённом primary-type=Single.
- [ ] RQ-воркер `cleanup_uploads` (TTL 30 минут).
- [ ] **Source matching**: после загрузки backend ищет тот же трек в открытых источниках (yt-dlp ytsearch/scsearch), показывает кандидатов в карточке верификации (см. [`14-user-upload.md`](14-user-upload.md:1) §3).
- [ ] Запись всех подтверждённых кандидатов в `track_sources` с правильным `recovery_priority` (публичные < `user_upload`).
- [ ] Фоновый воркер `match_user_uploads` (раз в сутки) — повторный поиск публичных источников для треков, у которых только `user_upload`.
- [ ] UI: вкладка «Загрузить файл», карточка верификации с предложениями метаданных и списком найденных источников; выбор primary.

**DoD:** пользователь загружает локальный mp3 → видит распознанные метаданные **и** список найденных публичных кандидатов (если есть) → подтверждает с выбором primary-источника → трек появляется в библиотеке, в индексе есть и `user_upload`, и публичные ссылки.

---

## Этап 4.2. Index & Restore (переносимая библиотека)
Подробности — [`16-library-index-and-restore.md`](16-library-index-and-restore.md:1).
- [ ] Миграция: таблица `track_sources`, поля `tracks.acoustid_fingerprint`, `tracks.cover_url_origin`.
- [ ] При создании трека (этапы 4 и 4.1) **всегда** пишем запись в `track_sources`.
- [ ] CLI: `index export` (jsonl + manifest, `--minimal/--include-covers/--include-secrets/--no-plays`).
- [ ] CLI: `index import --mode=skip-existing|overwrite|mirror` с обработкой конфликтов UUID/sha256.
- [ ] CLI: `library restore` (yt-dlp по сохранённым источникам, fallback через acoustid_fingerprint).
- [ ] Воркер `verify_sources` (раз в неделю, лёгкая проверка доступности ссылок).
- [ ] Admin/Master эндпоинты `/admin/index/*` и `/admin/library/*`.
- [ ] Расписание: ежедневный минимальный экспорт + еженедельный полный.
- [ ] JSON-схема `docs/schemas/library.schema.json` для валидации экспортов.

**DoD:** на чистом сервере по тарболу `library-*.tar.gz` можно восстановить структуру библиотеки (метаданные) и перекачать аудио для треков с живыми источниками; статистика по «протухшим» источникам видна master'у.

---

## Этап 4.3. External imports (Spotify / Yandex / Apple Music / file)
Подробности — [`17-external-imports.md`](17-external-imports.md:1).
- [ ] Миграция: таблицы `external_accounts`, `import_jobs`, `import_items`.
- [ ] Универсальный парсер CSV/JSON (Exportify, Soundiiz, TuneMyMusic, Spotify GDPR-экспорт).
- [ ] Spotify OAuth-адаптер (spotipy): liked tracks + playlists.
- [ ] Yandex Music adapter (yandex-music): неофициальный токен, лайки + плейлисты.
- [ ] (опц.) Apple Music через MusicKit + Developer JWT ES256.
- [ ] Track resolver: ISRC → mbid → локальный fuzzy → авто-загрузка (`match ≥ 0.85`) → `ambiguous`.
- [ ] RQ-воркер `process_import_job` с rate-limit для внешних API и yt-dlp.
- [ ] API `/import/*` (providers, connect, callback, file, jobs, items, resolve).
- [ ] UI «Импорт»: выбор источника, прогресс, очередь ambiguous с ручным выбором кандидата.
- [ ] Шифрование внешних токенов AES-GCM (мастер-ключ из `.env`), ротация без потери токенов.
- [ ] Идемпотентность: повторный импорт того же файла/плейлиста не создаёт дублей.

**DoD:** пользователь загружает CSV из Spotify-экспорта (или подключает OAuth) → создаются соответствующие плейлисты, треки автоматически скачиваются при уверенном матче, неразрешённые — попадают в очередь «ambiguous» для ручного выбора; повтор импорта идемпотентен.

---

## Этап 5. «Моя волна»
- [ ] mood_profiles, scorer, pool, session, feedback.
- [ ] Эндпоинты `/vibe/*`.
- [ ] UI главной страницы с настройками волны.
- [ ] Кнопки like/dislike/skip влияют на следующий батч.
- [ ] User-affinity счётчики в Redis + снимок в БД.

**DoD:** на главной можно включить волну, слушать ≥ 30 минут, реакции влияют на подбор (проверяется субъективно).

---

## Этап 6. iOS-приложение (базовое)
- [ ] Xcode-проект в `ios/`.
- [ ] Login + Keychain.
- [ ] APIClient (async/await).
- [ ] Catalog, Player (AVPlayer), Playlists.
- [ ] Background audio + Now Playing.
- [ ] Установка на личный iPhone через Xcode.
- [ ] (Опц.) TestFlight upload.

**DoD:** приложение собирается, ставится на iPhone владельца, можно слушать музыку из домашнего сервера.

---

## Этап 7. Полировка и стабилизация
- [ ] Cloudflare Tunnel настроен.
- [ ] HTTPS + Caddy в продакшн-варианте.
- [ ] Бэкапы по расписанию.
- [ ] Мониторинг (Uptime Kuma).
- [ ] Логи структурированы (JSON).
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
