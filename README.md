# WhatsApp Platform

[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
[![Python](https://img.shields.io/badge/Python-3.12+-3776AB?logo=python&logoColor=white)](backend/)
[![FastAPI](https://img.shields.io/badge/FastAPI-009688?logo=fastapi&logoColor=white)](backend/)
[![Next.js](https://img.shields.io/badge/Next.js-15-000000?logo=next.js&logoColor=white)](frontend/)
[![PostgreSQL](https://img.shields.io/badge/PostgreSQL-16-4169E1?logo=postgresql&logoColor=white)](docker/)
[![Redis](https://img.shields.io/badge/Redis-7-DC382D?logo=redis&logoColor=white)](docker/)
[![CI](https://img.shields.io/badge/CI-GitHub%20Actions-2088FF?logo=githubactions&logoColor=white)](.github/workflows/ci.yml)

> **WhatsApp Business automation** on the Meta Cloud API — webhooks, deterministic bot engine, conversation state, and a provider abstraction ready for production Meta credentials.

A modular platform: **FastAPI** backend, **PostgreSQL** persistence, **Redis**, and a **Next.js** admin shell for future operator tooling.

---

## Highlights

| | |
|---|---|
| **Webhook ingestion** | Meta-compatible GET/POST `/webhooks/whatsapp` |
| **Bot engine** | `/start`, `/help`, `/menu`, state machine, persistent sessions |
| **Idempotency** | Event- and message-level dedup in PostgreSQL |
| **Provider abstraction** | `mock` (default) or `meta` — swap via env, no code changes |
| **Tests** | 43+ automated tests, mock provider only |

---

## Status

| Area | Status |
|------|--------|
| Application foundation | Complete |
| WhatsApp integration (webhooks, provider abstraction, idempotency) | Complete |
| Deterministic bot engine and conversation state | Complete |
| Meta production credentials | Not configured (`WHATSAPP_PROVIDER=mock` by default) |
| Admin dashboard / read API | Planned |
| AI / LLM integration | Planned |
| Billing and analytics | Not started |

This repository is under active development. It is suitable for local development and integration testing, not production deployment without further hardening and configuration.

## Architecture

```
Meta webhook
    ↓
/webhooks/whatsapp
    ↓
Event parser → WhatsAppInboundEvent
    ↓
WebhookIdempotencyService (event-level dedup)
    ↓
MessageProcessingService
    ↓
Contact / Conversation / Message persistence
    ↓
BotEngine → BotRouter → command & state handlers
    ↓
BotResponse (channel-independent)
    ↓
OutboundMessageService
    ↓
WhatsAppProvider (mock | meta)
```

See [docs/architecture.md](docs/architecture.md) for layer boundaries, idempotency, and persistence details.

## Features (implemented)

- FastAPI application with structured logging and global error handling
- Health (`/health`) and readiness (`/ready`) endpoints
- PostgreSQL persistence with Alembic migrations
- Redis connectivity check on readiness
- WhatsApp webhook verification and event ingestion
- Provider abstraction with **mock** and **Meta** adapters
- Webhook- and message-level idempotency
- Deterministic bot commands: `/start`, `/help`, `/menu`, `/demo`
- Conversation state machine with persisted session state
- Inbound/outbound message records
- Comprehensive automated tests (mock provider; no real Meta calls)
- Docker Compose for local infrastructure
- GitHub Actions CI (lint, typecheck, tests, builds)

## Technology

| Layer | Stack |
|-------|-------|
| Backend API | Python 3.12+, FastAPI, Pydantic Settings, SQLAlchemy 2 (async), Alembic |
| Database | PostgreSQL 16 |
| Cache / queue prep | Redis 7 |
| HTTP client | httpx |
| Logging | structlog |
| Quality | ruff, mypy, pytest |
| Package manager | uv |
| Frontend shell | Next.js 15, React 19, TypeScript |
| Containers | Docker, Docker Compose |

## Repository structure

```
backend/           FastAPI app, bot engine, models, migrations, tests
frontend/          Next.js admin shell (minimal)
docker/            Compose files for dev and production-like stacks
docs/              Architecture and WhatsApp setup guides
scripts/           Development helpers
.github/workflows/ CI pipeline
.cursor/rules/     Cursor agent project rules
```

## Local development

### Prerequisites

| Tool | Version |
|------|---------|
| Python | 3.12+ (CI uses 3.12) |
| Node.js | 22+ |
| uv | latest |
| Docker | 24+ (recommended for Postgres and Redis) |
| Git | 2.40+ |

### 1. Configure environment

```bash
cp .env.example .env
# Edit .env if needed. Defaults work with Docker Compose services.
```

Never commit `.env`. Use `.env.example` as the template.

### 2. Start infrastructure

```bash
docker compose -f docker/docker-compose.dev.yml up -d postgres redis
```

### 3. Backend

```bash
cd backend
uv sync --extra dev
uv run alembic upgrade head
uv run uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

- API docs (development): [http://localhost:8000/docs](http://localhost:8000/docs)
- Liveness: `GET /health`
- Readiness: `GET /ready` (PostgreSQL + Redis)

### 4. Frontend

```bash
cd frontend
npm install
npm run dev
```

Open [http://localhost:3000](http://localhost:3000).

### 5. Full stack (Docker Compose)

```bash
docker compose -f docker/docker-compose.yml up --build
```

## Environment variables

All variables are documented in [`.env.example`](.env.example). Key groups:

| Group | Purpose |
|-------|---------|
| `DATABASE_URL`, `REDIS_URL` | Infrastructure connections |
| `WHATSAPP_PROVIDER` | `mock` (default) or `meta` |
| `WHATSAPP_VERIFY_TOKEN`, `WHATSAPP_APP_SECRET` | Webhook verification and signature validation |
| `META_WHATSAPP_*` | Meta Cloud API credentials (required only when `WHATSAPP_PROVIDER=meta`) |
| `SECRET_KEY` | Placeholder for future auth (Phase 2+) |

## Running

### Simulate an inbound WhatsApp message (mock provider)

```bash
curl -X POST http://localhost:8000/webhooks/whatsapp \
  -H "Content-Type: application/json" \
  -d @backend/tests/fixtures/whatsapp/text_message.json
```

Send a bot command:

```bash
# Edit the fixture text body to "/start" or use a JSON payload with command text
curl "http://localhost:8000/webhooks/whatsapp?hub.mode=subscribe&hub.verify_token=dev-verify-token&hub.challenge=test123"
```

## Testing

### Backend

```bash
cd backend
uv run ruff check app tests
uv run ruff format --check app tests
uv run mypy app
uv run pytest -v
```

### Frontend

```bash
cd frontend
npm run lint
npm run typecheck
npm run build
```

## Database

Migrations are managed with Alembic:

```bash
cd backend
uv run alembic upgrade head      # apply migrations
uv run alembic downgrade -1     # rollback one revision
uv run alembic history            # view history
```

Current migrations:

1. `001_initial_foundation` — admin users, business accounts, phone numbers
2. `002_webhook_events` — webhook idempotency table
3. `003_bot_conversations_messages` — contacts, conversations, sessions, messages

## Docker

| File | Purpose |
|------|---------|
| `docker/docker-compose.dev.yml` | Postgres + Redis (+ optional API with hot reload) |
| `docker/docker-compose.yml` | Full stack for production-like local runs |

Development Postgres credentials are `postgres` / `postgres` — for local use only.

## WhatsApp architecture

1. **Webhook layer** — validates requests, parses Meta payload, registers events.
2. **Idempotency** — `webhook_events.event_id` and `messages.wamid` unique constraints prevent duplicate processing.
3. **Message processing** — resolves contact and conversation, persists inbound message, invokes bot engine.
4. **Bot engine** — deterministic routing via command registry and state handlers; returns `BotResponse` objects.
5. **Outbound layer** — converts `BotResponse` to provider requests with bounded retries.

The bot engine does not call Meta directly. Switching providers requires configuration only (`WHATSAPP_PROVIDER=meta` + credentials).

See [docs/whatsapp-setup.md](docs/whatsapp-setup.md) for Meta app configuration.

## Security

- Do not commit secrets. Use `.env` locally and a secrets manager in production.
- Enable `WHATSAPP_APP_SECRET` signature validation before exposing webhooks publicly.
- Default `SECRET_KEY` and verify tokens are placeholders — change them for any shared environment.
- Structured logs must not include access tokens or raw credentials.
- Report security concerns via [SECURITY.md](SECURITY.md).

## Development workflow

1. Create a feature branch from `main` or `master`.
2. Make focused changes; run lint, typecheck, and tests locally.
3. Open a pull request with a clear description and test plan.
4. CI must pass before merge.

See [CONTRIBUTING.md](CONTRIBUTING.md) for detailed guidelines.

## Roadmap

| Phase | Scope |
|-------|-------|
| Admin read API | Conversations, messages, contacts for operator inbox |
| Admin UI | Dashboard wired to read API |
| AI integration | LLM provider behind existing bot extension points |
| Production hardening | Rate limits, observability, deployment runbooks |

## License

This project is licensed under the [MIT License](LICENSE).
