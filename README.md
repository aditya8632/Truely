# Document Access Grants Service

FastAPI + async SQLAlchemy (SQLAlchemy 2.0) + PostgreSQL.

## Features

- Create and revoke document access grants.
- Enforces:
  - `expires_at` must be at least 1 minute in the future
  - Only one *active* grant per `(granted_to_user_id, document_id)` pair
  - Only the grant creator can revoke
  - Cannot revoke revoked or expired grants
- Deterministic seed data for:
  - Users: Alice, Bob, Carol
  - Documents: Q1 Report, Product Roadmap, Budget 2026

## Requirements

- Python 3.11+
- Docker + docker-compose (recommended for the database)

## Local development (without Docker)

1. Create environment:

```bash
cp .env.example .env
```

2. Install dependencies:

```bash
python -m pip install -e ".[dev]"
```

3. Run migrations:

```bash
alembic upgrade head
```

4. Start the API:

```bash
uvicorn app.main:app --host 0.0.0.0 --port 8000
```

## Docker usage

Run the full stack (Postgres + API):

```bash
docker compose up --build
```

The API container runs `alembic upgrade head` automatically on startup.

## Migration commands

```bash
alembic upgrade head
alembic downgrade -1
```

Alembic reads `DATABASE_URL` from the environment.

## Tests

```bash
pytest -v
```

Unit tests run without a database. Integration tests require a reachable PostgreSQL instance
(Docker if needed).

## API

Base URL: `http://localhost:8000`

### Authentication / identity headers

This service uses headers for identity:

- `X-User-Id`: UUID of the current user (required for `POST /grants` and `DELETE /grants/{grant_id}`)
- `X-Now` (optional): ISO-8601 datetime used for time-sensitive logic and testing

### Create a grant

```bash
curl -i -X POST "http://localhost:8000/grants" \
  -H "Content-Type: application/json" \
  -H "X-User-Id: 11111111-1111-1111-1111-111111111111" \
  -d '{
    "document_id": "44444444-4444-4444-4444-444444444444",
    "granted_to_user_id": "22222222-2222-2222-2222-222222222222",
    "permission": "view",
    "expires_at": "2026-01-01T12:00:00Z"
  }'
```

### List grants

```bash
curl -i "http://localhost:8000/grants?granted_to_user_id=22222222-2222-2222-2222-222222222222&active_only=true"
```

### Retrieve a grant

```bash
curl -i "http://localhost:8000/grants/<grant_id>"
```

### Revoke a grant

```bash
curl -i -X DELETE "http://localhost:8000/grants/<grant_id>" \
  -H "X-User-Id: 11111111-1111-1111-1111-111111111111"
```

### Check active status

```bash
curl -i "http://localhost:8000/grants/<grant_id>/check"
```

