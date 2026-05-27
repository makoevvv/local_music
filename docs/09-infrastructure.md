# 09. Инфраструктура и деплой

## Целевая среда
Домашний **сервер** на macOS, постоянно включённый, домашняя сеть. Доступ извне — через **Cloudflare Tunnel** (рекомендация) или **Tailscale** (если нужен исключительно личный круг).

## Подготовка сервера

1. Отключить «Сон» (System Settings → Lock Screen / Battery → Prevent automatic sleeping).
2. Включить «Автоматический вход» (если без шифрования диска) или настроить unlock через `caffeinate` в `launchd`.
3. Установить:
   ```bash
   # Homebrew
   /bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
   brew install --cask docker
   brew install git ffmpeg
   ```
4. Запустить Docker Desktop. В настройках:
   - Resources: CPU 4, Memory 4-6 GB, Disk image 60+ GB.
   - Enable "Start Docker Desktop when you log in".
5. Создать постоянный пользовательский каталог, например `~/srv/local-music`. Туда — клон репозитория.

## Структура docker-compose

```yaml
# infra/docker-compose.yml (схема, конкретный yaml пишется на этапе 1)
services:
  postgres:       # PostgreSQL 16, volume: pgdata
  redis:          # Redis 7
  ytdlp-pot:      # PO Token для YouTube (bgutil), без cookies браузера
  backend:        # FastAPI (uvicorn), depends_on: postgres, redis, ytdlp-pot
  worker:         # rq worker, тот же образ, command=rq worker ...
  web:            # сборка React (либо отдельный nginx-static-контейнер)
  caddy:          # reverse proxy, ports: 80, 443
  # профиль compose `proxy` (если YouTube недоступен напрямую из Docker):
  proxy:          # sing-box VLESS → локальный SOCKS :1080
  # опционально:
  minio:          # если STORAGE_BACKEND=s3
  uptime-kuma:    # мониторинг
```

Тома:
- `pgdata` → `/var/lib/postgresql/data`
- `storage` → `/data/storage` (биндим в `~/srv/local-music/data/storage` для удобства бэкапа)
- `caddy_data`, `caddy_config`

## Запуск
```bash
cp .env.example .env  # отредактировать; при VPN: YTDLP_PROXY=socks5h://proxy:1080
# sing-box: cp infra/proxy/sing-box.config.json.example infra/proxy/sing-box.config.json
docker compose -p local_music -f infra/docker-compose.yml --profile proxy up -d --build
docker compose -p local_music -f infra/docker-compose.yml exec backend alembic upgrade head
docker compose -p local_music -f infra/docker-compose.yml exec backend python -m app.cli init-master
```

См. также [`infra/proxy/README.md`](../infra/proxy/README.md) (VLESS, `ytdlp-pot`, cookies не нужны).

## Reverse proxy (Caddy)

`infra/Caddyfile`:
```
{$DOMAIN} {
    encode zstd gzip

    @api path /api/* /openapi.json /docs /redoc /ws/*
    handle @api {
        reverse_proxy backend:8000
    }

    handle {
        root * /srv/web
        try_files {path} /index.html
        file_server
    }
}
```

Если без домена — слушаем 80 без TLS (только в локалке).

## Внешний доступ

### Вариант 1: Cloudflare Tunnel (рекомендуется)
- Бесплатно, без проброса портов, без статического IP.
- Шаги:
  1. Зарегистрировать домен в Cloudflare (или перенести NS).
  2. `brew install cloudflared`.
  3. `cloudflared tunnel login` → создать tunnel → получить creds.
  4. Запустить как сервис: `cloudflared service install`.
  5. Привязать `music.example.com` → `http://localhost:80`.
- Бонус: Cloudflare Access (PIN/email) перед сайтом — дополнительный слой защиты.

### Вариант 2: Tailscale
- Своя VPN. Доступ только с устройств в tailnet.
- Подходит, если сервис строго для своего узкого круга.
- iOS-клиент должен быть в той же tailnet.

### Вариант 3: Проброс портов на роутере
- Не рекомендуется (динамический IP, безопасность).

## Бэкапы

1. **БД** — ежедневный `pg_dump`:
   ```bash
   # infra/scripts/backup_db.sh
   docker compose exec -T postgres pg_dump -U $POSTGRES_USER $POSTGRES_DB | gzip > backups/db_$(date +%F).sql.gz
   ```
2. **Аудио** — `rsync -a data/storage/ /Volumes/ExternalBackup/local-music/storage/`.
3. **Library index** (см. [`16-library-index-and-restore.md`](16-library-index-and-restore.md:1)) — переносимый дамп метаданных + источников:
   ```bash
   # ежедневно — минимальный
   docker compose exec -T backend python -m app.cli index export --minimal \
     --out /data/exports/library-$(date +%F).jsonl.gz
   # еженедельно — полный
   docker compose exec -T backend python -m app.cli index export --include-covers \
     --out /data/exports/library-full-$(date +%F).tar.gz
   ```
4. Запуск из `launchd` или `crontab -e`:
   ```
   0 3 * * *  cd ~/srv/local-music && ./infra/scripts/backup_db.sh
   15 3 * * * cd ~/srv/local-music && ./infra/scripts/export_index.sh
   ```
5. Хранить не менее 7 ежедневных + 4 еженедельных. Индекс компактный (мегабайты) — копию рекомендуется держать вне сервера (приватный репо/облако/флешка).

## Логи и мониторинг

- `docker compose logs -f --tail=200 backend`.
- Уровень логирования backend регулируется через `LOG_LEVEL` (INFO/DEBUG).
- Опционально: Uptime Kuma в отдельном контейнере для health-check.
- Опционально: Loki + Promtail + Grafana — если захочется красивых дашбордов (вне MVP).

## Безопасность инфраструктуры

- `.env` хранится только локально, в git **не коммитим**.
- Открытые наружу порты: только 443 через Cloudflare Tunnel; локально 80 — для разработки.
- Пароли БД / Redis — длинные случайные.
- Регулярные обновления образов (`docker compose pull && up -d` раз в неделю).
- Auto-restart: все контейнеры с `restart: unless-stopped`.

## CI (GitHub Actions)

`.github/workflows/`:
- `backend.yml`: pytest + ruff + mypy на каждый push в `main`/PR.
- `web.yml`: typecheck + eslint + build.
- `docker.yml`: сборка образов и push в GHCR при тегах `v*.*.*`.
- `ios.yml` (опционально): build на macOS-runner, при тегах `ios-v*`.

## CD (опционально)
- На сервере поставить `watchtower` или простой cron-скрипт:
  ```bash
  cd ~/srv/local-music && git pull && docker compose pull && docker compose up -d
  ```
- Запускать вручную или раз в сутки.
