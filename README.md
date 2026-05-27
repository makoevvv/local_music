# 🎵 Local Music — личный музыкальный сервис

Персональный сервис для прослушивания музыки без цензуры с возможностью поиска треков в интернете, формирования внутренней библиотеки, плейлистов и «волны» (vibe-радио).

> Сервис рассчитан на узкий круг пользователей (себя и нескольких друзей). Развёртывается на домашнем сервере.

> 🤖 **Работа с ИИ-агентом:**
> - При первом запуске нового чата — промпт в [`START_PROMPT.md`](START_PROMPT.md).
> - Текущую задачу формулируй в [`CURRENT_TASK.md`](CURRENT_TASK.md) (агент читает его первым в каждом запросе).

## 📦 Состав проекта

| Компонент | Технология | Папка / документ |
|---|---|---|
| Backend API | Python 3.12 + FastAPI | [`backend/`](backend/) |
| Web-клиент | React + TypeScript + Vite | [`web/`](web/) |
| iOS-приложение (план) | SwiftUI | [`docs/10-mobile-apps.md`](docs/10-mobile-apps.md) |
| Android-приложение (план) | Kotlin + Jetpack Compose | [`docs/10-mobile-apps.md`](docs/10-mobile-apps.md) |
| Инфраструктура | Docker Compose | [`infra/`](infra/) |
| VPN / YouTube (опц.) | sing-box + yt-dlp PO Token | [`infra/proxy/README.md`](infra/proxy/README.md) |
| Документация | Markdown | [`docs/`](docs/README.md) |

## 🚀 Быстрый старт

```bash
git clone https://github.com/makoevvv/local_music.git
cd local_music
cp .env.example .env
# отредактировать .env; для Search/download из YouTube — см. infra/proxy/README.md

docker compose -p local_music -f infra/docker-compose.yml --profile proxy up -d --build
docker compose -p local_music -f infra/docker-compose.yml exec backend alembic upgrade head
docker compose -p local_music -f infra/docker-compose.yml exec backend python -m app.cli init-master

cd web && pnpm install && pnpm dev
```

После старта:

- Web: http://localhost:3000 (Vite dev server, отдельно от compose)
- API: http://localhost:8000/docs (Swagger UI)

Подробнее: [`docs/13-development-guide.md`](docs/13-development-guide.md), [`docs/09-infrastructure.md`](docs/09-infrastructure.md).

## 📚 Документация

Вся проектная информация — в [`docs/README.md`](docs/README.md). Ключевые документы:

- [`docs/00-overview.md`](docs/00-overview.md) — обзор проекта и цели
- [`docs/01-requirements.md`](docs/01-requirements.md) — требования и user stories
- [`docs/02-architecture.md`](docs/02-architecture.md) — архитектура системы
- [`docs/03-tech-stack.md`](docs/03-tech-stack.md) — стек технологий и обоснование
- [`docs/04-database-schema.md`](docs/04-database-schema.md) — схема БД
- [`docs/05-api-spec.md`](docs/05-api-spec.md) — спецификация REST API
- [`docs/06-music-sourcing.md`](docs/06-music-sourcing.md) — поиск и загрузка музыки
- [`docs/07-vibe-recommendations.md`](docs/07-vibe-recommendations.md) — «моя волна»
- [`docs/08-shazam-integration.md`](docs/08-shazam-integration.md) — Shazam
- [`docs/09-infrastructure.md`](docs/09-infrastructure.md) — инфраструктура / деплой
- [`docs/10-mobile-apps.md`](docs/10-mobile-apps.md) — iOS/Android, TestFlight
- [`docs/11-security-legal.md`](docs/11-security-legal.md) — безопасность и правовые аспекты
- [`docs/12-roadmap.md`](docs/12-roadmap.md) — план разработки
- [`docs/13-development-guide.md`](docs/13-development-guide.md) — гайд разработчика
- [`docs/14-user-upload.md`](docs/14-user-upload.md) — ручная загрузка треков и верификация
- [`docs/15-master-account.md`](docs/15-master-account.md) — мастер-аккаунт (owner)
- [`docs/16-library-index-and-restore.md`](docs/16-library-index-and-restore.md) — индекс библиотеки и восстановление
- [`docs/17-external-imports.md`](docs/17-external-imports.md) — импорт из Spotify, Yandex, Apple Music и др.

## 🧭 Текущий статус

| Этап | Статус |
|---|---|
| 0–3 | ✅ в `main` — PR [#1](https://github.com/makoevvv/local_music/pull/1), [#2](https://github.com/makoevvv/local_music/pull/2), [#3](https://github.com/makoevvv/local_music/pull/3) |
| 4. Поиск и загрузка | ✅ в ветке `stage/4-search-download`, PR [#4](https://github.com/makoevvv/local_music/pull/4) (ещё не вмержен) |
| 4.2 Index & Restore | 🔜 следующий — см. [`CURRENT_TASK.md`](CURRENT_TASK.md) |
| 4.1 Ручная загрузка | запланирован после 4.2 — [`docs/14-user-upload.md`](docs/14-user-upload.md) |

Детали по этапам: [`docs/12-roadmap.md`](docs/12-roadmap.md).

## ⚖️ Лицензия и оговорка

Проект исключительно для личного использования. См. [`docs/11-security-legal.md`](docs/11-security-legal.md).
