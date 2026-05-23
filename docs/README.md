# 📚 Документация проекта Local Music

Эта папка — **единый источник правды** по проекту. Все решения, схемы, планы и инструкции должны фиксироваться здесь. Цель — чтобы любой разработчик (включая ИИ-агента в новом контексте) мог открыть `docs/` и быстро понять, что и как делать.

## Структура

| Файл | Содержание |
|---|---|
| [`00-overview.md`](00-overview.md:1) | Обзор проекта, цели, не-цели, аудитория |
| [`01-requirements.md`](01-requirements.md:1) | Функциональные/нефункциональные требования, user stories |
| [`02-architecture.md`](02-architecture.md:1) | Общая архитектура, компоненты, диаграммы |
| [`03-tech-stack.md`](03-tech-stack.md:1) | Технологический стек и обоснование выбора |
| [`04-database-schema.md`](04-database-schema.md:1) | Схема БД, ER-диаграмма, миграции |
| [`05-api-spec.md`](05-api-spec.md:1) | REST API: эндпоинты, контракты |
| [`06-music-sourcing.md`](06-music-sourcing.md:1) | Поиск, скачивание и нормализация музыки |
| [`07-vibe-recommendations.md`](07-vibe-recommendations.md:1) | «Моя волна» — алгоритм рекомендаций |
| [`08-shazam-integration.md`](08-shazam-integration.md:1) | Интеграция Shazam |
| [`09-infrastructure.md`](09-infrastructure.md:1) | Docker, деплой на сервер, бэкапы |
| [`10-mobile-apps.md`](10-mobile-apps.md:1) | iOS/Android, TestFlight, sideload |
| [`11-security-legal.md`](11-security-legal.md:1) | Безопасность, авторизация, правовые аспекты |
| [`12-roadmap.md`](12-roadmap.md:1) | Этапы разработки, milestones, чек-листы |
| [`13-development-guide.md`](13-development-guide.md:1) | Гайд: как поднять, как контрибьютить |
| [`14-user-upload.md`](14-user-upload.md:1) | Ручная загрузка треков и верификация |
| [`15-master-account.md`](15-master-account.md:1) | Мастер-аккаунт (owner): правила и реализация |
| [`16-library-index-and-restore.md`](16-library-index-and-restore.md:1) | Индекс библиотеки и восстановление при переносе |
| [`17-external-imports.md`](17-external-imports.md:1) | Импорт треков/плейлистов из Spotify, Yandex, Apple Music и т.д. |
| [`adr/`](adr/) | Architecture Decision Records — записи о ключевых решениях |

## Правила работы с документацией

1. **Любое архитектурное решение** фиксируется в [`adr/`](adr/) (формат: `NNNN-short-title.md`).
2. При **изменении API** — обновить [`05-api-spec.md`](05-api-spec.md:1).
3. При **изменении схемы БД** — обновить [`04-database-schema.md`](04-database-schema.md:1) **до** написания миграции.
4. Каждый завершённый этап в [`12-roadmap.md`](12-roadmap.md:1) — отмечается `[x]`.
5. Документы пишутся на русском, идентификаторы (имена таблиц, полей, эндпоинтов) — на английском.
