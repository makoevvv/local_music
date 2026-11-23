# CURRENT_TASK — текущая задача для ИИ-агента

> **Как пользоваться:** см. шапку в исторических архивах (`docs/tasks-archive/`). ИИ читает этот файл **первым**.

---

## 🎯 Что нужно сделать

**Рекомендация:** сначала **этап 4.2** (Index & Restore), затем **4.1** (ручная загрузка). См. §«Почему 4.2 раньше 4.1» ниже.

Этап 4 (search + download) закрыт — архив: [`docs/tasks-archive/2026-05-27-stage-4-search-download.md`](docs/tasks-archive/2026-05-27-stage-4-search-download.md:1).

---

## 🤔 Зачем

После этапа 4 треки есть в каталоге, но **library index** (`track_sources`, export/import) ещё нет — при переносе сервера восстановление по источникам ограничено полями `tracks.source_*`.

---

## 📚 Контекст и ссылки

- [`docs/16-library-index-and-restore.md`](docs/16-library-index-and-restore.md:1)
- [`docs/12-roadmap.md`](docs/12-roadmap.md:95) §«Этап 4.2»
- [`docs/04-database-schema.md`](docs/04-database-schema.md:124) §`track_sources`

---

## ✅ Критерии готовности (этап 4.2, кратко)

- [ ] Миграция `track_sources` + запись при download/upload.
- [ ] CLI `index export` / `index import` / `library restore`.
- [ ] Admin API `/admin/index/*` (master).
- [ ] DoD: восстановление библиотеки из дампа на чистом сервере.

---

## 🚧 Ограничения и нюансы

- На этапе 4 **не** писали в `track_sources` — это нормально; backfill при внедрении 4.2.
- Коммит/PR этапа 4 — по запросу владельца.

---

## Почему 4.2 раньше 4.1

1. Уже есть треки из Search — им нужен `track_sources` и export, иначе перенос/бэкап библиотеки слабый.
2. Этап 4.1 в спецификации **сразу пишет в `track_sources`** — проще один раз сделать таблицу в 4.2, чем потом переделывать upload.
3. 4.1 (AcoustID, upload UI) — отдельный большой блок; его можно строить поверх готового индекса.

## ❓ Открытые вопросы

—

---

## 📦 Ожидаемые артефакты

—

---

## 📝 Лог работы по задаче

—
