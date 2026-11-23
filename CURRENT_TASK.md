# CURRENT_TASK — текущая задача для ИИ-агента

> **Как пользоваться:** см. шапку в исторических архивах (`docs/tasks-archive/`). ИИ читает этот файл **первым**.

---

## 🎯 Что нужно сделать

Этап **4.1** — ручная загрузка треков и верификация ([`docs/14-user-upload.md`](docs/14-user-upload.md:1), [`docs/12-roadmap.md`](docs/12-roadmap.md:79)).

Этапы 4 и 4.2 закрыты в ветках/PR (search/download + library index). Перед 4.1 убедись, что `stage/4-search-download` и 4.2 вмержены или работай поверх актуальной feature-ветки с `track_sources`.

---

## 🤔 Зачем

Пользователь должен иметь возможность загрузить локальный файл, получить предложения метаданных (AcoustID/MusicBrainz) и публичные источники для индекса, подтвердить трек в библиотеке.

---

## 📚 Контекст и ссылки

- [`docs/14-user-upload.md`](docs/14-user-upload.md:1)
- [`docs/16-library-index-and-restore.md`](docs/16-library-index-and-restore.md:1) — `track_sources` уже есть
- [`docs/06-music-sourcing.md`](docs/06-music-sourcing.md:1) — tier / recovery_priority
- Архив 4.2: [`docs/tasks-archive/2026-08-08-stage-4-2-index-restore.md`](docs/tasks-archive/2026-08-08-stage-4-2-index-restore.md:1)

---

## ✅ Критерии готовности (кратко)

Из roadmap §4.1:

- [ ] `/tracks/upload`, verify, confirm
- [ ] mutagen + fpcalc/AcoustID
- [ ] trust levels, album resolution
- [ ] source matching → `track_sources`
- [ ] UI загрузки и карточка верификации

---

## 🚧 Ограничения и нюансы

- Не ломать library index (4.2): upload обязан писать `user_upload` (+ публичные источники).
- Ветка: от актуального tip с этапами 4+4.2.

---

## ❓ Открытые вопросы

—

---

## 📦 Ожидаемые артефакты

—

---

## 📝 Лог работы по задаче

- Этап 4.2 реализован: миграция `track_sources`, CLI index/library, admin API, schema, export cron script.
