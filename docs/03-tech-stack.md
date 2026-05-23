# 03. Технологический стек

## Принципы выбора
1. Уважение к предпочтениям владельца: **Python, Docker, Java, C++**.
2. Минимизация количества языков в MVP — фокус на Python.
3. Open-source.
4. Хорошая документация и большое комьюнити.

## Стек

### Backend
| Категория | Технология | Версия | Зачем |
|---|---|---|---|
| Язык | Python | 3.12 | Основной язык backend |
| Фреймворк | **FastAPI** | 0.110+ | Async, OpenAPI, типизация |
| ORM | SQLAlchemy | 2.x (async) | Стандарт de facto |
| Миграции | Alembic | — | Управление схемой |
| Валидация | Pydantic | 2.x | Уже внутри FastAPI |
| Конфиг | pydantic-settings | — | Типизированный `.env` |
| Очередь | RQ | — | Простая очередь на Redis |
| HTTP-клиент | httpx | — | Async + sync |
| Тесты | pytest, pytest-asyncio, httpx | — | — |
| Линт/формат | ruff, black, mypy | — | — |
| Загрузчик | yt-dlp | — | Скачивание из открытых источников |
| Аудио | ffmpeg, mutagen | — | Транскод и теги |
| Аудио-фичи | librosa (опц.) | — | BPM, энергия для vibe |

### Web (frontend)
| Категория | Технология |
|---|---|
| Язык | TypeScript 5 |
| Фреймворк | React 18 |
| Сборщик | Vite |
| Стиль | Tailwind CSS |
| Состояние | Zustand |
| Запросы | TanStack Query (React Query) |
| Роутинг | React Router 6 |
| UI-компоненты | shadcn/ui (Radix + Tailwind) |
| Плеер | HTML5 `<audio>` + кастомный UI |

### iOS
| Категория | Технология |
|---|---|
| Язык | Swift 5.10+ |
| UI | SwiftUI |
| Минимальный iOS | 16.0 |
| Плеер | AVPlayer + MPNowPlayingInfoCenter |
| Сеть | URLSession + async/await |
| Декодирование JSON | Codable |
| Хранилище | UserDefaults + Keychain (для токенов) |

### Android (опционально, после MVP)
| Категория | Технология |
|---|---|
| Язык | Kotlin |
| UI | Jetpack Compose |
| Плеер | ExoPlayer (Media3) |
| Сеть | Ktor client / Retrofit |
| DI | Hilt |
| Минимальный SDK | 26 (Android 8) |

### Инфраструктура
| Категория | Технология |
|---|---|
| Контейнеры | Docker, Docker Compose |
| База данных | PostgreSQL 16 |
| Кеш / очередь | Redis 7 |
| Reverse proxy | Caddy 2 |
| Внешний доступ | Cloudflare Tunnel (или Tailscale) |
| Мониторинг | Uptime Kuma (опц.), Loki + Grafana (опц.) |
| Бэкапы | rsync + cron, pg_dump |
| CI | GitHub Actions |

## Где может пригодиться C++ / Java
Стек MVP — Python. Но в проекте есть точки расширения:

- **C++:**
  - Микросервис для тяжёлой обработки аудио (BPM-детектор, спектральный анализ, аудио-отпечатки в духе chromaprint).
  - Кастомный fingerprinting-сервис как альтернатива Shazam.
  - Архитектура (отдельный сервис в docker-compose) это позволит без переделок.

- **Java:**
  - Native Android-приложение (Kotlin/Java).
  - Возможный отдельный сервис для тегов через JAudioTagger.

Решения такого типа фиксируются как ADR в [`adr/`](adr/).

## Версионирование и lockfiles
- Python: `uv` или `pip-tools` → `requirements.lock`.
- JS: `pnpm` → `pnpm-lock.yaml`.
- Все версии — фиксированные.

## Стиль кода
- Python: `ruff` (E,F,I,UP,B,SIM) + `black` (line-length 100) + `mypy --strict` для services/.
- TS: ESLint + Prettier.
- Swift: SwiftLint.
- Pre-commit hooks: `pre-commit` — настраивается в этапе 1.
