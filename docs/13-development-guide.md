# 13. Гайд разработчика

## 1. Создание GitHub-репозитория

Текущая папка `/Users/ruslanmakoev/Documents/local_music` ещё не под git. Сделаем её репо и запушим на GitHub.

### Шаг 1. Создать репозиторий на GitHub
- Открыть https://github.com/new
- Имя: `local-music` (или другое).
- Visibility: **Private** (рекомендуется).
- **НЕ** добавлять README/.gitignore/LICENSE — они уже есть локально.

### Шаг 2. Инициализация локально
```bash
cd ~/Documents/local_music
git init -b main
git add .
git commit -m "chore: initial project docs and structure"
git remote add origin git@github.com:<your-username>/local-music.git
git push -u origin main
```

### Шаг 3. Защита веток (опц.)
В Settings → Branches → защитить `main`: требовать PR, требовать прохождение CI.

### Шаг 4. SSH-ключ (если ещё нет)
```bash
ssh-keygen -t ed25519 -C "you@example.com"
cat ~/.ssh/id_ed25519.pub  # добавить в GitHub → Settings → SSH keys
```

## 2. Структура репозитория (целевая)

```
local-music/
├── README.md
├── .env.example
├── .gitignore
├── docs/                      # документация (этот каталог)
│   └── adr/
├── backend/
│   ├── app/
│   │   ├── api/
│   │   ├── core/
│   │   ├── models/
│   │   ├── repositories/
│   │   ├── services/
│   │   ├── workers/
│   │   ├── cli.py
│   │   └── main.py
│   ├── alembic/
│   ├── tests/
│   ├── pyproject.toml
│   └── Dockerfile
├── web/
│   ├── src/
│   ├── public/
│   ├── package.json
│   └── vite.config.ts
├── ios/                       # Xcode-проект
├── android/                   # (после MVP)
├── infra/
│   ├── docker-compose.yml
│   ├── Caddyfile
│   └── scripts/
│       └── backup_db.sh
└── .github/
    └── workflows/
        ├── backend.yml
        └── web.yml
```

## 3. Команды для повседневной работы

### Backend
```bash
cd backend
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"

# линт/форматирование
ruff check . && ruff format .
mypy app

# тесты
pytest

# запуск локально (без Docker)
uvicorn app.main:app --reload --port 8000

# импорт локального аудиофайла в каталог (этап 3+)
python -m app.cli import-track --file /path/to/track.mp3 --title "Title" --artist "Artist" --user-id <uuid>
```

### Web
```bash
cd web
pnpm install
pnpm dev          # http://localhost:3000
pnpm build
pnpm typecheck
```

### Docker (вся система)
```bash
cp .env.example .env
docker compose -f infra/docker-compose.yml up -d --build
docker compose -f infra/docker-compose.yml logs -f backend
docker compose -f infra/docker-compose.yml exec backend alembic upgrade head
docker compose -f infra/docker-compose.yml exec backend python -m app.cli init-master
```

### Миграции
```bash
# создать новую миграцию
docker compose exec backend alembic revision --autogenerate -m "add tracks table"
# применить
docker compose exec backend alembic upgrade head
# откатить на одну
docker compose exec backend alembic downgrade -1
```

## 4. Git-флоу

- `main` — стабильная ветка.
- Фичи: `stage/N-feature-slug` (например, `stage/2-auth`).
- Коммиты — Conventional Commits:
  - `feat: add login endpoint`
  - `fix: handle expired refresh token`
  - `docs: update roadmap`
  - `chore: bump deps`
  - `refactor: extract player hook`
- PR содержит: что, зачем, как тестировать. Связан с этапом из [`12-roadmap.md`](12-roadmap.md:1).

## 5. Работа с ИИ-агентом (важно)

Чтобы ограничение контекста чата не мешало:
1. **Никогда не описывать решения только в чате** — всё фиксируется в `docs/`.
2. Когда начинается новый этап — открываем соответствующий раздел [`12-roadmap.md`](12-roadmap.md:1) и работаем по чек-листу.
3. Новые архитектурные решения → ADR в [`adr/`](adr/).
4. После каждого мерджа в main → коротко обновить статусы в roadmap и `README`.
5. При перезаходе в новый чат: дать агенту прочитать [`docs/README.md`](README.md:1) — он восстановит контекст.

## 6. ADR (Architecture Decision Record)

Шаблон в [`adr/0000-template.md`](adr/0000-template.md:1). Создавать на любое **значимое** решение: выбор библиотеки, изменение архитектуры, отказ от фичи.

## 7. Testing strategy
- Backend:
  - Unit-тесты для services (mocked repos).
  - Интеграционные с реальным postgres+redis (testcontainers или `docker compose -f compose.test.yml`).
  - Контрактные тесты для API (httpx + pytest).
- Web:
  - Vitest для утилит и хуков.
  - Playwright (опц.) для e2e ключевых сценариев.
- iOS:
  - XCTest для модели/нетворка.
  - Snapshot-тесты — опционально.

## 8. Полезные команды macOS

```bash
# не давать серверу засыпать
caffeinate -dis &

# смотреть, что слушает порт
sudo lsof -i :8000

# размер storage
du -sh ~/srv/local-music/data/storage
```
