# WhatsApp Platform

[![Latest release](https://img.shields.io/github/v/release/D1bakar/whats_up?include_prereleases&sort=semver)](https://github.com/D1bakar/whats_up/releases)
[![CI](https://github.com/D1bakar/whats_up/actions/workflows/ci.yml/badge.svg)](https://github.com/D1bakar/whats_up/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
[![GitHub stars](https://img.shields.io/github/stars/D1bakar/whats_up?style=social)](https://github.com/D1bakar/whats_up/stargazers)
[![GitHub forks](https://img.shields.io/github/forks/D1bakar/whats_up?style=social)](https://github.com/D1bakar/whats_up/forks)
[![GitHub watchers](https://img.shields.io/github/watchers/D1bakar/whats_up?style=social)](https://github.com/D1bakar/whats_up/watchers)

[![Python](https://img.shields.io/badge/Python-3.12+-3776AB?logo=python&logoColor=white)](backend/)
[![FastAPI](https://img.shields.io/badge/FastAPI-009688?logo=fastapi&logoColor=white)](backend/)
[![Ollama](https://img.shields.io/badge/Ollama-local%20LLM-black)](https://ollama.com/)
[![Next.js](https://img.shields.io/badge/Next.js-15-000000?logo=next.js&logoColor=white)](frontend/)
[![PostgreSQL](https://img.shields.io/badge/PostgreSQL-16-4169E1?logo=postgresql&logoColor=white)](docker/)
[![Redis](https://img.shields.io/badge/Redis-7-DC382D?logo=redis&logoColor=white)](docker/)
[![Docker](https://img.shields.io/badge/Docker-Compose-2496ED?logo=docker&logoColor=white)](docker/)

> **WhatsApp Business automation** — webhooks, deterministic bot engine, **AI orchestration** (Ollama / OpenAI / mock), conversation persistence, and provider abstractions ready for production Meta credentials.

A modular platform: **FastAPI** backend, **PostgreSQL** persistence, **Redis**, and a **Next.js** admin shell for future operator tooling.

**⭐ Star · 🍴 Fork · 👁 Watch** — [github.com/D1bakar/whats_up](https://github.com/D1bakar/whats_up)

---

## Languages & tech stack

GitHub may group small languages under **Other** in the sidebar. This project uses **all** of the following:

| Language / tech | Share | Used for |
|-----------------|-------|----------|
| ![Python](https://img.shields.io/badge/Python-97%25-3776AB?logo=python&logoColor=white) | ~97% | Backend API, bot engine, tests, migrations |
| ![TypeScript](https://img.shields.io/badge/TypeScript-1%25-3178C6?logo=typescript&logoColor=white) | ~1% | Next.js admin frontend |
| ![Docker](https://img.shields.io/badge/Dockerfile-1%25-2496ED?logo=docker&logoColor=white) | ~1% | Container images |
| ![CSS](https://img.shields.io/badge/CSS-<1%25-1572B6?logo=css3&logoColor=white) | <1% | Frontend styles |
| ![Shell](https://img.shields.io/badge/Shell-<1%25-4EAA25?logo=gnu-bash&logoColor=white) | <1% | Dev scripts |
| ![JavaScript](https://img.shields.io/badge/JavaScript-<1%25-F7DF1E?logo=javascript&logoColor=black) | <1% | Frontend tooling |

**Infrastructure & data:** PostgreSQL 16 · Redis 7 · Alembic · SQL · YAML (CI/Compose)

See [docs/production-readiness.md](docs/production-readiness.md) for the full path to an industry-ready deployment.

---

## Highlights

| | |
|---|---|
| **Webhook ingestion** | Meta-compatible GET/POST `/webhooks/whatsapp` |
| **Bot engine** | `/start`, `/help`, `/menu`, state machine, persistent sessions |
| **AI layer** | Ollama (local), OpenAI, or mock — orchestrator with limits and fallback |
| **Idempotency** | Event- and message-level dedup in PostgreSQL |
| **Provider abstraction** | WhatsApp: `mock` \| `meta` · AI: `mock` \| `ollama` \| `openai` |
| **Tests** | 75+ automated tests; mock HTTP — no live API keys required |

---

## Status

| Area | Status |
|------|--------|
| Application foundation | Complete |
| WhatsApp integration (webhooks, provider abstraction, idempotency) | Complete |
| Deterministic bot engine and conversation state | Complete |
| AI layer (Ollama, OpenAI, mock orchestration) | Complete |
| Meta production credentials | Not configured (`WHATSAPP_PROVIDER=mock` by default) |
| Admin dashboard / read API | Planned |
| Billing and analytics | Not started |

**Track production work:** [Open issues](https://github.com/D1bakar/whats_up/issues?q=is%3Aissue+label%3Aproduction) · [Production readiness checklist](docs/production-readiness.md)

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
BotEngine → BotRouter → command & state handlers (deterministic)
              └→ AITextHandler → AIOrchestrator → Ollama | OpenAI | mock
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
| `AI_PROVIDER` | `mock` (default), `ollama`, `openai`, or `disabled` |
| `OLLAMA_BASE_URL`, `OLLAMA_MODEL`, `OLLAMA_REQUEST_TIMEOUT` | Local Ollama (`phi3:mini`, 120s default timeout) |
| `OPENAI_API_KEY`, `AI_MODEL`, `AI_REQUEST_TIMEOUT` | Cloud OpenAI (60s default timeout) |
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
| Production hardening | Rate limits, observability, deployment runbooks |

## Releases

See [Releases](https://github.com/D1bakar/whats_up/releases) for version history.

| Version | Highlights |
|---------|------------|
| **v0.2.0** | AI layer, Ollama provider, orchestrator, deployment guide |
| v0.1.0 | Foundation, WhatsApp webhooks, bot engine |

## License

This project is licensed under the [MIT License](LICENSE).
