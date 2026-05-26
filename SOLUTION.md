# Solution Overview

This project implements a **Document Access Grants Service** using:

- **FastAPI** for the REST API
- **SQLAlchemy 2.0 async** + **asyncpg** for PostgreSQL persistence
- **Alembic** for schema migrations + deterministic seed data
- **Pydantic v2** for request/response validation
- **pytest** + **pytest-asyncio** for unit/integration testing
- **Docker Compose** for local Postgres + API orchestration

## Architecture decisions

- **Service layer** (`app/services/grants.py`) owns business rules:
  - expiry validation (minimum 1 minute)
  - “only one active grant per pair”
  - revoke authorization and state transitions
- **Repository layer** (`app/repositories/grants.py`) owns SQLAlchemy queries and updates.
- **Dependency injection** (`app/dependencies.py`) wires:
  - `AsyncSession` per request
  - `GrantService`
  - current user identity from `X-User-Id`
  - a time source from optional `X-Now` header (useful for deterministic tests)

## Async SQLAlchemy setup

- `app/core/database.py` defines:
  - `Base` (SQLAlchemy Declarative Base)
  - `engine` (async engine)
  - `SessionLocal` (async sessionmaker)
  - `session_scope()` dependency for request-scoped sessions
- Repositories use `await session.execute(...)` and `async with session.begin()` in the service for correct transaction boundaries.

## Grant validation strategy

### API validation (Pydantic v2)

`app/schemas/grant.py` validates:

- `expires_at` must be **timezone-aware**
- `expires_at >= now + 1 minute` (checked at validation time)

### Business rules (service layer)

`app/services/grants.py` enforces runtime rules using a captured `now` value:

- **Active** means:
  - `revoked_at IS NULL`
  - `expires_at > now`
- **Only one active grant per pair**:
  - repository query checks for an existing active grant for the `(granted_to_user_id, document_id)` pair
  - if found, service returns `409 Conflict`
- **Revoke rules**:
  - `revoked_at` already set -> `409 Conflict`
  - `expires_at <= now` -> `400 Bad Request`
  - requester not `granted_by_user_id` -> `403 Forbidden`

## Partial unique index reasoning

PostgreSQL indexes cannot express a fully time-dynamic “active” predicate that automatically updates when time passes.
To keep the constraint meaningful and production-friendly, this service uses:

- A **partial unique index** enforcing: only one grant row per `(granted_to_user_id, document_id)` where `revoked_at IS NULL`.

To ensure the “active = not revoked AND not expired” semantics are respected for *creation*, the service performs internal housekeeping:

- On `POST /grants`, it marks any expired (but not yet revoked) grants for the same pair as revoked before inserting the new grant.

This makes the partial uniqueness constraint align with the service’s “active” definition without requiring background jobs or cron tasks.

Tradeoff:

- Expired grants may end up with `revoked_at` set as a result of creation-time housekeeping. They remain permanently stored, and they are still correctly treated as inactive for all API operations.

## Testing strategy

### Unit tests

`tests/unit/test_grant_service.py` covers:

- Pydantic `expires_at` validation
- duplicate active grant prevention
- revoke authorization
- revoke expired handling

Unit tests do not require a database; they use a fake repository/session.

### Integration tests

`tests/integration/test_grants_api.py` runs against **real PostgreSQL** using `httpx.AsyncClient` against the FastAPI ASGI app:

- tests for create/list/get/check/revoke endpoints
- tests for status codes and payloads
- revoke authorization and expired revoke behavior

The test bootstrap will attempt to start the provided `docker-compose.yml` stack when Postgres is not reachable.

## Tradeoffs / notes

- Identity/auth is header-based (`X-User-Id`) to keep the service self-contained.
- `X-Now` is supported to make time-based behavior testable and deterministic; it is optional and defaults to real UTC time.

