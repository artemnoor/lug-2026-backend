# LUG 2026 backend

Новый backend ЛУГ 2026 — production-oriented modular monolith на FastAPI,
SQLAlchemy 2.x и Alembic. Reference implementation находится отдельно в
[`artemnoor/lug-2026`](https://github.com/artemnoor/lug-2026) и не является
частью runtime этого проекта.

## Что реализовано

- вертикальные модули `auth`, `users`, `teams`, `media`, `portfolio`, `video`,
  `notifications`, `content` и admin façade;
- legacy `/api/*` HTTP-контракты, cookie-сессия `lug_session`, CSRF cookie/header
  и camelCase projections для существующего frontend;
- PostgreSQL как deployment database, SQLite как локальный deterministic adapter;
- typed Pydantic request/response models, единый error envelope и generated
  OpenAPI;
- Argon2id password hashing с read-only compatibility для legacy scrypt;
- private local/S3 uploads, bounded streaming, MIME/magic validation, optional
  scanner и выдача только после `scan_status=clean`;
- structured JSON logs, request/trace IDs, bounded metrics, liveness/readiness и
  rate-limiter seam для Redis.

## Требования и локальный запуск

Нужны Python 3.11+ и pip. Для стандартного локального режима:

```powershell
py -3.11 -m venv .venv
\.venv\Scripts\Activate.ps1
python -m pip install -e ".[dev]"
Copy-Item .env.example .env
alembic upgrade head
python -m uvicorn app.main:app --reload --host 127.0.0.1 --port 4174
```

`Settings.from_env()` читает `.env`, а переменные процесса имеют приоритет.
Development defaults используют SQLite, local storage, log email и in-memory
rate limiter. Bootstrap admin создаётся из `LUG_ADMIN_EMAIL`/
`LUG_ADMIN_PASSWORD`; эти значения по умолчанию разрешены только в development.

Для PostgreSQL/Redis/S3/SMTP задайте соответствующие параметры из
[`.env.example`](.env.example). Production/staging configuration намеренно
отказывается стартовать с SQLite, wildcard hosts, короткими secrets, неявным
operations token или logging verification codes.

## Миграции и запуск через Docker

Миграция `0001_initial_schema` создаёт таблицы и индексы через явные Alembic
operations; startup не выполняет DDL. Для локального полного окружения:

```powershell
docker compose up --build
```

Compose поднимает только реальные зависимости текущего backend: API, PostgreSQL
и Redis. S3 и SMTP подключаются внешней конфигурацией, а не добавляются как
фиктивные сервисы.

## Проверки

```powershell
python -m pytest -q
ruff format --check app tests alembic
ruff check app tests alembic
mypy app
```

Или используйте `make verify`, если установлен `make`. Migration test выполняет
clean upgrade → downgrade → upgrade на SQLite. PostgreSQL smoke следует запускать
через Compose или отдельный PostgreSQL URL.

## API и документация

- `GET /health` — только liveness процесса;
- `GET /ready` — проверка database/rate limiter/storage (в hardened окружении
  нужен operations bearer token);
- `/docs`, `/redoc`, `/openapi.json` — generated contract;
- `/api/openapi.json`, `/healthz`, `/readyz`, `/livez` — compatibility aliases;
- подробные границы модулей — [`ARCHITECTURE.md`](ARCHITECTURE.md);
- forensic audit и endpoint matrix — [`docs/forensic-audit.md`](docs/forensic-audit.md)
  и [`docs/compatibility-matrix.md`](docs/compatibility-matrix.md).

## Структура

```text
app/
  main.py                  # composition root
  api_models/              # HTTP contracts
  core/                    # config, UoW, errors, HTTP policy, security
  db/                      # SQLAlchemy metadata and rows
  infrastructure/          # storage and email adapters
  modules/<domain>/        # API + application + contracts/ports + infrastructure
alembic/                   # explicit schema migrations
tests/                     # API, security, architecture, migration regression
```

Frontend в этот backend не переносится. Его фактические API assumptions сохранены
в compatibility matrix и проверены regression/API tests.
