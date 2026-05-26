# Архив задачи — 2026-05-27

Закрытая итерация. Копия `CURRENT_TASK.md` на момент завершения; PR [#1](https://github.com/makoevvv/local_music/pull/1) смержен в `main`.

---

## 🎯 Что нужно было сделать

Этап 1 из [`docs/12-roadmap.md`](../12-roadmap.md:19) — скелет backend на FastAPI, Docker-инфраструктура и базовый CI.

---

## ✅ Критерии готовности (итоговое состояние)

- [x] Структура `backend/`, `pyproject.toml`, health-check, config, async Postgres/Redis.
- [x] Alembic + миграция `users` (минимальный набор без `is_master`).
- [x] `infra/docker-compose.yml`, `Dockerfile`, GitHub Actions CI.
- [x] DoD проверен владельцем: `docker compose up`, `alembic upgrade head`, `curl /health` → `{"status":"ok"}`; CI зелёный.

---

## 📝 Лог работы

- Ветка `stage/1-backend-skeleton`, коммит `ddc5e6b`, merge `0c075a2`.
- Новых ADR не потребовалось (FastAPI — ADR-0001).
