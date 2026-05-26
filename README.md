# 🎵 Local Music — личный музыкальный сервис

Персональный сервис для прослушивания музыки без цензуры с возможностью поиска треков в интернете, формирования внутренней библиотеки, плейлистов и «волны» (vibe-радио).

> Сервис рассчитан на узкий круг пользователей (себя и нескольких друзей). Развёртывается на домашнем сервере.

> 🤖 **Работа с ИИ-агентом:**
> - При первом запуске нового чата — скопируй промпт из [`START_PROMPT.md`](START_PROMPT.md:1).
> - Текущую задачу формулируй в [`CURRENT_TASK.md`](CURRENT_TASK.md:1) (агент читает его первым в каждом запросе).

## 📦 Состав проекта

| Компонент | Технология | Папка |
|---|---|---|
| Backend API | Python 3.12 + FastAPI | [`backend/`](backend/) |
| Web-клиент | React + TypeScript + Vite | [`web/`](web/) |
| iOS-приложение | SwiftUI | [`ios/`](ios/) |
| Android-приложение (опционально) | Kotlin + Jetpack Compose | [`android/`](android/) |
| Инфраструктура | Docker Compose | [`infra/`](infra/) |
| Документация | Markdown | [`docs/`](docs/) |

## 🚀 Быстрый старт

```bash
git clone https://github.com/<your-username>/local-music.git
cd local-music
cp .env.example .env
docker compose up -d
```

После старта:
- Web: http://localhost:3000
- API: http://localhost:8000/docs (Swagger UI)

## 📚 Документация

Вся проектная информация хранится в [`docs/`](docs/README.md). Ключевые документы:

- [`docs/00-overview.md`](docs/00-overview.md:1) — обзор проекта и цели
- [`docs/01-requirements.md`](docs/01-requirements.md:1) — требования и user stories
- [`docs/02-architecture.md`](docs/02-architecture.md:1) — архитектура системы
- [`docs/03-tech-stack.md`](docs/03-tech-stack.md:1) — стек технологий и обоснование
- [`docs/04-database-schema.md`](docs/04-database-schema.md:1) — схема БД
- [`docs/05-api-spec.md`](docs/05-api-spec.md:1) — спецификация REST API
- [`docs/06-music-sourcing.md`](docs/06-music-sourcing.md:1) — поиск и загрузка музыки
- [`docs/07-vibe-recommendations.md`](docs/07-vibe-recommendations.md:1) — «моя волна»
- [`docs/08-shazam-integration.md`](docs/08-shazam-integration.md:1) — Shazam
- [`docs/09-infrastructure.md`](docs/09-infrastructure.md:1) — инфраструктура / деплой
- [`docs/10-mobile-apps.md`](docs/10-mobile-apps.md:1) — iOS/Android, TestFlight
- [`docs/11-security-legal.md`](docs/11-security-legal.md:1) — безопасность и правовые аспекты
- [`docs/12-roadmap.md`](docs/12-roadmap.md:1) — план разработки
- [`docs/13-development-guide.md`](docs/13-development-guide.md:1) — гайд разработчика
- [`docs/14-user-upload.md`](docs/14-user-upload.md:1) — ручная загрузка треков и верификация
- [`docs/15-master-account.md`](docs/15-master-account.md:1) — мастер-аккаунт (owner)
- [`docs/16-library-index-and-restore.md`](docs/16-library-index-and-restore.md:1) — индекс библиотеки и восстановление
- [`docs/17-external-imports.md`](docs/17-external-imports.md:1) — импорт из Spotify, Yandex, Apple Music и др.

## 🧭 Текущий статус

Этап: **2. Auth** — реализован в ветке `stage/2-auth` (ожидает PR). Следующий: Этап 3 — каталог.

## ⚖️ Лицензия и оговорка

Проект исключительно для личного использования. См. [`docs/11-security-legal.md`](docs/11-security-legal.md:1).
