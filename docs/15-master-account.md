# 15. Мастер-аккаунт (owner)

## Концепция

В системе существует ровно **один master-аккаунт** — суперпользователь владельца сервиса. Он:
- создаётся при первичной инициализации;
- **не может быть удалён** никем, включая самого себя;
- **не может потерять master-статус** (флаг неизменяем после создания);
- может редактировать любые собственные данные, кроме master-статуса;
- имеет полный доступ ко всем операциям (CRUD над пользователями, треками, плейлистами, аудит-логом).

## Отличия от обычного `admin`

| Возможность | `user` | `admin` | `master` |
|---|---|---|---|
| Слушать, создавать плейлисты | ✅ | ✅ | ✅ |
| Удалять треки из общей библиотеки | ❌ | ✅ | ✅ |
| Создавать invite-коды | ❌ | ✅ | ✅ |
| Создавать/удалять обычных пользователей | ❌ | ✅ | ✅ |
| Назначать роль `admin` | ❌ | ❌ | ✅ |
| Снимать роль `admin` | ❌ | ❌ | ✅ |
| Удалять `admin`-пользователей | ❌ | ❌ | ✅ |
| Просматривать полный аудит-лог | ❌ | частично | ✅ |
| Менять системные настройки | ❌ | ❌ | ✅ |
| Быть удалённым | ✅ | ✅ | ❌ |
| Потерять свой статус | — | ✅ (admin → user) | ❌ |

Роль `admin` в проекте — резервная (например, для друга, которому даём расширенные права). В MVP может не использоваться вовсе, но архитектура её поддерживает.

## Изменения в БД

В таблицу `users` ([`04-database-schema.md`](04-database-schema.md:1)) добавляется:

```sql
ALTER TABLE users
  ADD COLUMN is_master boolean NOT NULL DEFAULT false;

-- Не больше одного master в системе:
CREATE UNIQUE INDEX users_single_master_idx
  ON users ((1))
  WHERE is_master = true;
```

Поле `role` остаётся (`'user' | 'admin'`), `is_master` — отдельный неизменяемый флаг.

### Триггеры/инварианты (на уровне БД)

```sql
-- Запрет удаления master-аккаунта
CREATE OR REPLACE FUNCTION prevent_master_delete() RETURNS trigger AS $$
BEGIN
  IF OLD.is_master THEN
    RAISE EXCEPTION 'master account cannot be deleted';
  END IF;
  RETURN OLD;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trg_prevent_master_delete
  BEFORE DELETE ON users
  FOR EACH ROW EXECUTE FUNCTION prevent_master_delete();

-- Запрет изменения is_master после создания
CREATE OR REPLACE FUNCTION prevent_master_flag_change() RETURNS trigger AS $$
BEGIN
  IF OLD.is_master IS DISTINCT FROM NEW.is_master THEN
    RAISE EXCEPTION 'is_master flag is immutable';
  END IF;
  -- Также запрет деактивации master:
  IF OLD.is_master AND NEW.is_active = false THEN
    RAISE EXCEPTION 'master account cannot be deactivated';
  END IF;
  RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trg_prevent_master_flag_change
  BEFORE UPDATE ON users
  FOR EACH ROW EXECUTE FUNCTION prevent_master_flag_change();
```

Триггеры — двойная страховка к проверкам в коде, чтобы даже прямой SQL не сломал инвариант.

## Создание master-аккаунта

Только через CLI на сервере, один раз:

```bash
docker compose exec backend python -m app.cli init-master \
  --email owner@example.com \
  --username owner \
  --password-stdin
```

Команда:
1. Проверяет, что master ещё не существует. Если есть — отказ.
2. Создаёт пользователя `is_master=true`, `role='admin'`, `is_active=true`.
3. Пишет запись в `audit_log` (`action='master.created'`).

Повторный вызов команды → ошибка. Восстановление мастера при потере доступа — см. §6.

## Авторизация в коде

```python
# app/core/security.py (схема)

def require_master(user: User = Depends(get_current_user)) -> User:
    if not user.is_master:
        raise HTTPException(403, "Master role required")
    return user

def require_admin(user: User = Depends(get_current_user)) -> User:
    if user.is_master:
        return user
    if user.role != "admin" or not user.is_active:
        raise HTTPException(403, "Admin role required")
    return user
```

В эндпоинтах:
- Все `/admin/*` — `Depends(require_admin)`.
- Эндпоинты управления ролями и удаления admin-ов — `Depends(require_master)`.
- Эндпоинт `PATCH /admin/users/{id}`:
  - При попытке `is_master=true/false` → 403 (флаг неизменяем).
  - При попытке изменить master другим пользователем → 403.
  - Master может менять свои email/username/password.

## Изменения в API ([`05-api-spec.md`](05-api-spec.md:1))

Расширяем раздел Admin:

| Метод | Путь | Кто | Описание |
|---|---|---|---|
| GET    | `/admin/users` | admin/master | список |
| POST   | `/admin/users` | master | создать пользователя без invite |
| PATCH  | `/admin/users/{id}` | admin/master | базовое редактирование |
| PATCH  | `/admin/users/{id}/role` | **master** | назначить/снять `admin` |
| DELETE | `/admin/users/{id}` | master | удалить; запрещено для master |
| POST   | `/admin/invites` | admin/master | создать invite |
| GET    | `/admin/audit-log` | master | полный лог |
| GET    | `/admin/stats` | admin/master | статистика |
| PATCH  | `/auth/me` | self | master тоже использует этот же эндпоинт; `is_master` всегда игнорируется в payload |

В ответах `/auth/me` и `/admin/users` всегда возвращается `is_master: bool` — UI рисует пометку «owner».

## UI

- На странице профиля master-аккаунта виден бейдж «Owner» и подсказка «Этот аккаунт нельзя удалить, master-статус неизменяем».
- В списке пользователей master помечен иконкой, кнопки «удалить» и «снять admin» отключены для него.
- Поля редактирования профиля master такие же, как у обычного пользователя; чекбокса «master» нет вовсе.

## Безопасность

- Master-токены — те же JWT, что и у обычных пользователей; никаких бессрочных. Refresh короче (например, 7 дней вместо 30) для снижения риска.
- При логине master — обязательная запись в `audit_log` (`action='master.login'`, IP, user-agent).
- Все mutating-операции, инициированные master, логируются.
- Желательно (опционально на этапе 7): двухфакторная аутентификация (TOTP) для master.

## Восстановление при потере пароля

Поскольку master нельзя удалить, восстановление — через сервер:

1. SSH на сервер → `docker compose exec backend python -m app.cli reset-master-password`.
2. Команда читает новый пароль из stdin, обновляет `password_hash`. Пишет в `audit_log`.

Эта команда работает только локально (нет HTTP-эндпоинта).

## Влияние на существующие документы

- [`04-database-schema.md`](04-database-schema.md:1): добавить колонку `users.is_master` и описание триггеров.
- [`05-api-spec.md`](05-api-spec.md:1): расширить раздел Admin (см. выше).
- [`11-security-legal.md`](11-security-legal.md:1): пункт «Master-аккаунт — отдельные правила, обязательный аудит, опц. 2FA».
- [`12-roadmap.md`](12-roadmap.md:1): в этап 2 (Auth) добавить пункт «реализовать master-аккаунт и CLI `init-master`».
- [`13-development-guide.md`](13-development-guide.md:1): обновить инструкцию первого запуска — заменить `create-admin` на `init-master`.
