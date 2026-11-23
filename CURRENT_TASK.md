# CURRENT_TASK — текущая задача для ИИ-агента

> **Как пользоваться:** см. шапку в исторических архивах (`docs/tasks-archive/`). ИИ читает этот файл **первым**.

---

## 🎯 Что нужно сделать

Этап **4.3** — импорт из внешних сервисов ([`docs/17-external-imports.md`](docs/17-external-imports.md:1), [`docs/12-roadmap.md`](docs/12-roadmap.md:1)).

Этапы 4, 4.2 и 4.1 закрыты в ветках/PR (поиск, индекс библиотеки, ручная загрузка). Перед 4.3 работай поверх актуального tip с `track_sources` и upload API.

---

## 🤔 Зачем

Пользователь должен перенести лайки и плейлисты из Spotify, Яндекс Музыки или CSV, не создавая дубликаты.

---

## 📚 Контекст и ссылки

- [`docs/17-external-imports.md`](docs/17-external-imports.md:1)
- [`docs/14-user-upload.md`](docs/14-user-upload.md:1) — source matching уже есть, импорт не должен его копировать
- Архив 4.1: [`docs/tasks-archive/2026-11-24-stage-4-1-user-upload.md`](docs/tasks-archive/2026-11-24-stage-4-1-user-upload.md:1)

---

## ✅ Критерии готовности (кратко)

Из roadmap §4.3: таблицы импорта, парсер CSV/JSON, Spotify и Yandex адаптеры, резолвер треков, API `/import/*`, UI очереди ambiguous, идемпотентность.

---

## 🚧 Ограничения и нюансы

- Не ломать upload и library index.
- Apple Music в чек-листе помечен как опциональный.

---

## ❓ Открытые вопросы

—

---

## 📦 Ожидаемые артефакты

—

---

## 📝 Лог работы по задаче

- Этап 4.1: upload/verify/confirm, AcoustID, album resolution, source matching, cleanup/reconcile/match workers, web-вкладка загрузки.
