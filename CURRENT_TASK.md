# CURRENT_TASK — текущая задача для ИИ-агента

> **Как пользоваться:** см. шапку в исторических архивах (`docs/tasks-archive/`). ИИ читает этот файл **первым**.

---

## 🎯 Что нужно сделать

Этап **7** — оставшаяся полировка ([`docs/12-roadmap.md`](docs/12-roadmap.md:1)).

Уже есть профиль compose `edge`: Caddy (`infra/Caddyfile`) и `cloudflared`. Токен туннеля владелец кладёт в `CLOUDFLARE_TUNNEL_TOKEN`. Установку iOS на iPhone не повторять.

Дальше по чек-листу, не всё сразу:

1. Бэкапы по расписанию (`infra/scripts/backup_db.sh` и cron из [`docs/09-infrastructure.md`](docs/09-infrastructure.md:1)).
2. Uptime Kuma.
3. JSON-логи backend.
4. Покрытие тестами критичных модулей ≥ 60%.
5. README и прогон «как поднять» с нуля.

---

## 🤔 Зачем

Сервис снаружи по HTTPS и с предсказуемыми бэкапами, логами и проверками.

---

## 📚 Контекст и ссылки

- [`docs/09-infrastructure.md`](docs/09-infrastructure.md:1)
- [`docs/11-security-legal.md`](docs/11-security-legal.md:1)
- [`docs/12-roadmap.md`](docs/12-roadmap.md:1) — этап 7

---

## ✅ Критерии готовности (кратко)

DoD этапа целиком: сервис живёт неделю, открывается снаружи с iPhone, бэкапы появляются каждый день. Этот срез закрывает только Caddy и туннель в репозитории.

---

## ❓ Открытые вопросы

—

---

## 📝 Лог работы по задаче

- Профиль `edge`: Caddy (:80 и :443 `tls internal`) и `cloudflared` с токеном из env.
- Не сделано: cron бэкапов, Uptime Kuma, JSON-логи, порог покрытия, проверка README с нуля.
