# Changelog

All notable changes to this project are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [0.2.0] - 2026-08-13

### Added

- **AI layer** — provider abstraction, orchestrator, context builder, versioned prompts, abuse limits
- **AI providers** — `mock`, `openai` (httpx adapter), **`ollama`** (local `/api/chat`, e.g. `phi3:mini`)
- Provider-aware timeouts: `OLLAMA_REQUEST_TIMEOUT=120`, `AI_REQUEST_TIMEOUT=60`
- Bot integration — natural language → AI; `/start`, `/help`, `/menu` remain deterministic
- AI test suite (`tests/test_ai_layer.py`, `tests/test_ollama_provider.py`)
- Optional live Ollama integration test (`RUN_OLLAMA_INTEGRATION=1`)
- Pipeline verification script (`backend/scripts/verify_ollama_pipeline.py`)
- Deployment guide (`docs/deployment.md`) and CD workflow for GHCR image publishing
- GitHub Release workflow (`.github/workflows/release.yml`)

### Changed

- `.env.example` expanded with full AI and Ollama configuration
- Architecture and production-readiness documentation updated
- README badges, status table, and release links refreshed

## [0.1.0] - 2026-08-13

### Added

- Application foundation: FastAPI, PostgreSQL, Redis, Alembic, health endpoints
- WhatsApp integration: provider abstraction, webhooks, idempotency, mock provider
- Deterministic bot engine: commands, conversation state, message pipeline
- Next.js admin shell (scaffold)
- Docker Compose dev and production-like stacks
- GitHub Actions CI: ruff, mypy, pytest, frontend build
- Documentation: architecture, contributing, security policy

[Unreleased]: https://github.com/D1bakar/whats_up/compare/v0.2.0...HEAD
[0.2.0]: https://github.com/D1bakar/whats_up/compare/v0.1.0...v0.2.0
[0.1.0]: https://github.com/D1bakar/whats_up/releases/tag/v0.1.0
