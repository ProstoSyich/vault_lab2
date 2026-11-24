# Vault

Backend-сервис управления пользователями и OAuth-клиентами: REST-аутентификация по JWT (HS256), GraphQL API для админки, аудит действий и минимальная SPA администратора на vanilla JS.

Стек: FastAPI, SQLAlchemy 2.x, Alembic, Ariadne (schema-first GraphQL), Argon2id + pepper + zxcvbn, python-jose, SQLite, pytest.

## Установка

Требуется Python 3.11–3.12 (проект проверен на 3.12).

```bash
python -m venv .venv
# Windows
.venv\Scripts\activate
# Linux / macOS
source .venv/bin/activate

pip install -r requirements.txt
```

## Настройка

```bash
cp .env.example .env
```

Заполните `JWT_SECRET` и `PASSWORD_PEPPER` длинными случайными строками (например, `python -c "import secrets; print(secrets.token_urlsafe(48))"`). Остальные параметры можно оставить по умолчанию.

| Переменная | Назначение |
|---|---|
| `DATABASE_URL` | строка подключения SQLAlchemy |
| `JWT_SECRET` | секрет подписи JWT |
| `JWT_ALGORITHM` | алгоритм, по умолчанию `HS256` |
| `ACCESS_TOKEN_TTL_MIN` | время жизни access-токена в минутах |
| `PASSWORD_PEPPER` | глобальный pepper для Argon2id |
| `PASSWORD_MIN_LENGTH` | минимальная длина пароля |
| `ENVIRONMENT`, `APP_NAME` | служебные поля |
| `LOG_LEVEL` | уровень логирования (`INFO` по умолчанию) |

`.env` и файлы `*.db` в репозиторий не попадают.

## Миграции и запуск

```bash
alembic upgrade head
python run.py
```

- Админка: http://127.0.0.1:8000/admin/
- GraphQL Playground: http://127.0.0.1:8000/graphql
- OpenAPI: http://127.0.0.1:8000/docs

Первая регистрация выполняется через `POST /auth/register` или GraphQL-мутацию `registerUser`. Права администратора выдаются скриптом:

```bash
python scripts/make_admin.py --email user@example.com
```

## Проверка API

Регистрация и логин:

```bash
curl -X POST http://127.0.0.1:8000/auth/register \
  -H "Content-Type: application/json" \
  -d "{\"email\":\"user@example.com\",\"password\":\"correct-horse-battery-staple-42\"}"
```

Запрос `{ me { email } }` с заголовком `Authorization: Bearer <token>`:

```json
{
  "data": {
    "me": {
      "email": "user@example.com"
    }
  }
}
```

Запросы админки:

```graphql
query {
  users(search: "user@", limit: 20) { id email isActive isAdmin createdAt }
  clients { clientId name isConfidential redirectUris createdAt }
  auditEvents(eventType: "user.login.success", limit: 20) {
    eventType actorId ip metadata createdAt
  }
}

mutation {
  createClient(name: "Demo App", isConfidential: true) { clientId name }
}
```

Доступ к `users`, `clients`, `auditEvents`, `createClient` и `disableUser` защищён директивой `@isAdmin`, к `me` — `@isAuthenticated`.

## Структура

```
app/
├── main.py              # FastAPI, монтирование REST, GraphQL и статики
├── config.py            # настройки из .env (pydantic-settings)
├── db/                  # Base, движок, фабрика сессий, get_db
├── models/              # User, OAuthClient, AuditEvent (SQLAlchemy 2.x)
├── core/                # пароли, JWT, зависимости, логирование
├── auth/                # /auth/register, /auth/login, /auth/me
├── audit/               # единая функция записи аудита
├── graphql/             # SDL-схема, резолверы, контекст, директивы
└── static/              # SPA администратора (index.html, app.js)
alembic/                 # миграции
scripts/make_admin.py    # выдача прав администратора
tests/                   # pytest
run.py                   # запуск uvicorn
```

## Тесты

```bash
pytest -q
```

Тесты используют отдельную SQLite-базу во временной директории и не затрагивают `vault.db`.

## Логирование

Приложение пишет этапы работы через стандартный `logging`: старт/остановку, регистрацию, попытки входа и события аудита. Пароли, хэши, токены и client secrets в логи и `audit_events.metadata_json` не записываются.
