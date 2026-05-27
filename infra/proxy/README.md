# Прокси для поиска и скачивания (VLESS → SOCKS5)

`yt-dlp` не понимает VLESS напрямую. Схема:

```
backend / worker  →  SOCKS5 (sing-box в Docker)  →  VLESS  →  ваш VPN-сервер  →  YouTube
```

## Быстрый старт

1. Скопируйте пример и подставьте параметры из вашего VLESS-конфига (или из ссылки `vless://…`):

```bash
cp infra/proxy/sing-box.config.json.example infra/proxy/sing-box.config.json
# отредактируйте server, uuid, tls / reality
```

2. В корневом `.env`:

```env
YTDLP_PROXY=socks5h://proxy:1080
```

`socks5h` — DNS тоже через прокси (для YouTube это важно).

3. Запуск с профилем `proxy`:

```bash
docker compose -f infra/docker-compose.yml --profile proxy up -d --build
```

Сервис `proxy` доступен в сети compose как hostname `proxy`, порт `1080`.

## Проверка

```bash
docker compose -f infra/docker-compose.yml --profile proxy exec backend \
  curl -I --max-time 15 -x socks5h://proxy:1080 https://www.youtube.com
```

Должен вернуться `HTTP/2 200` или `301`/`302`, не таймаут.

Поиск в UI: запрос «Blondie» → список кандидатов.

## Без Docker (sing-box на Mac)

Если клиент уже слушает, например, `127.0.0.1:10808`:

```env
YTDLP_PROXY=socks5h://host.docker.internal:10808
```

Профиль `proxy` в compose не нужен.

## Reality vs обычный TLS

В `sing-box.config.json.example` включён блок **Reality** — типичный для VLESS-серверов. Если у вас только TLS + SNI (без Reality), удалите секцию `"reality": { … }` и задайте корректный `server_name`.

Параметры должны **совпадать** с сервером: `uuid`, `flow` (`xtls-rprx-vision` или пусто), `public_key`, `short_id`, SNI.

## Скачивание YouTube без cookies браузера

В `docker-compose` поднимается сервис **`ytdlp-pot`** (Proof-of-Origin Token). Backend/worker подключаются к нему автоматически (`YTDLP_POT_BASE_URL=http://ytdlp-pot:4416`). Ручной экспорт cookies **не нужен**.

Если скачивание всё же падает, опционально можно задать `YTDLP_COOKIES_FILE` в `.env` (см. `.env.example`).

## Безопасность

`infra/proxy/sing-box.config.json` в `.gitignore` — не коммитьте UUID и ключи.  
`ytdlp-cookies.txt` тоже не коммитьте (сессия YouTube).
