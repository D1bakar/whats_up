# WhatsApp Platform

[![CI](https://github.com/D1bakar/whats_up/actions/workflows/ci.yml/badge.svg)](https://github.com/D1bakar/whats_up/actions/workflows/ci.yml) [![Latest release](https://img.shields.io/github/v/release/D1bakar/whats_up)](https://github.com/D1bakar/whats_up/releases) [![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)

A modular WhatsApp Business automation platform built with FastAPI, PostgreSQL, Redis, and Next.js. It combines reliable webhook processing, a deterministic bot engine, and pluggable AI providers behind clean provider boundaries.

> Under active development: ready for local development and integration testing. Review the production-readiness checklist before deploying publicly.

## Highlights

- Meta-compatible WhatsApp webhook verification and event ingestion
- Persistent contacts, conversations, sessions, and messages
- Deterministic commands: /start, /help, /menu, and /demo
- AI orchestration with mock, Ollama, OpenAI, or disabled providers
- Mock and Meta WhatsApp provider adapters
- PostgreSQL-backed event and message idempotency
- Health and readiness endpoints, structured logging, and automated tests
- Docker Compose and GitHub Actions CI

## Architecture

Meta webhook -> parser -> idempotency -> message processing -> persistence -> bot engine -> AI orchestrator -> WhatsApp provider

The bot engine never calls Meta directly. Webhook handlers stay thin, business logic lives in application services, and duplicate events are protected by database constraints. See [docs/architecture.md](docs/architecture.md).

## Tech stack

| Layer | Technologies |
| --- | --- |
| Backend | Python 3.12+, FastAPI, Pydantic Settings, SQLAlchemy 2 async, httpx |
| Data | PostgreSQL 16, Redis 7, Alembic |
| AI | Ollama, OpenAI, mock provider |
| Frontend | Next.js 15, React 19, TypeScript |
| Quality | ruff, mypy, pytest, GitHub Actions |
| Runtime | Docker, Docker Compose, uv |

## Quick start

### Prerequisites

Python 3.12+, Node.js 22+, uv, Docker 24+, and Git.

### 1. Configure the environment

    cp .env.example .env

    The defaults use the mock WhatsApp provider. Never commit .env; use [.env.example](.env.example) for placeholders.

    ### 2. Start PostgreSQL and Redis

        docker compose -f docker/docker-compose.dev.yml up -d postgres redis

        ### 3. Start the backend

            cd backend
                uv sync --extra dev
                    uv run alembic upgrade head
                        uv run uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

                        API docs: http://localhost:8000/docs. Liveness: GET /health. Readiness: GET /ready.

                        ### 4. Start the frontend

                            cd frontend
                                npm install
                                    npm run dev

                                    Open http://localhost:3000.

                                    ### Full stack with Docker

                                        docker compose -f docker/docker-compose.yml up --build

                                        ## Configuration

                                        All settings are documented in [.env.example](.env.example). Important options include WHATSAPP_PROVIDER (mock or meta), AI_PROVIDER (mock, ollama, openai, or disabled), DATABASE_URL, REDIS_URL, WHATSAPP_VERIFY_TOKEN, WHATSAPP_APP_SECRET, and META_WHATSAPP_* credentials.

                                        To connect a real Meta application, follow [docs/whatsapp-setup.md](docs/whatsapp-setup.md).

                                        ## Try the webhook locally

                                            curl "http://localhost:8000/webhooks/whatsapp?hub.mode=subscribe&hub.verify_token=dev-verify-token&hub.challenge=test123"

                                                curl -X POST http://localhost:8000/webhooks/whatsapp -H "Content-Type: application/json" -d @backend/tests/fixtures/whatsapp/text_message.json

                                                ## Development and testing

                                                    cd backend
                                                        uv run ruff check app tests
                                                            uv run ruff format --check app tests
                                                                uv run mypy app
                                                                    uv run pytest -v

                                                                    Frontend checks: npm run lint, npm run typecheck, and npm run build.

                                                                    ## Repository layout

                                                                        backend/           FastAPI app, bot engine, models, migrations, and tests
                                                                            frontend/          Next.js admin shell
                                                                                docker/            Compose files
                                                                                    docs/              Architecture and setup guides
                                                                                        scripts/            Development helpers
                                                                                            .github/workflows/ CI pipeline

                                                                                            ## Roadmap

                                                                                            - Complete the operator-facing admin inbox and dashboard
                                                                                            - Add production rate limiting and expanded observability
                                                                                            - Add deployment runbooks and operational tooling
                                                                                            - Continue billing and analytics work

                                                                                            Track progress in [issues](https://github.com/D1bakar/whats_up/issues) and the [production-readiness checklist](docs/production-readiness.md).

                                                                                            ## Contributing and license

                                                                                            Focused pull requests are welcome. Read [CONTRIBUTING.md](CONTRIBUTING.md), run the relevant checks, and include a test plan. For security concerns, see [SECURITY.md](SECURITY.md). This project is available under the [MIT License](LICENSE).

                                                                                            ## Releases

                                                                                            - **v0.2.0** — AI layer, Ollama provider, orchestrator, and deployment guidance
                                                                                            - **v0.1.0** — Foundation, WhatsApp webhooks, and deterministic bot engine

                                                                                            See [all releases](https://github.com/D1bakar/whats_up/releases).
