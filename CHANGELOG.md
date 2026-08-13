# Changelog

All notable changes to this project are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added
- MIT license and polished README with tech badges
- GitHub issue/PR templates and production readiness checklist
- `.gitattributes` for accurate GitHub language detection

## [0.1.0] - 2026-08-13

### Added
- Application foundation: FastAPI, PostgreSQL, Redis, Alembic, health endpoints
- WhatsApp integration: provider abstraction, webhooks, idempotency, mock provider
- Deterministic bot engine: commands, conversation state, message pipeline
- Next.js admin shell (scaffold)
- Docker Compose dev and production-like stacks
- GitHub Actions CI: ruff, mypy, pytest, frontend build
- Documentation: architecture, contributing, security policy

[Unreleased]: https://github.com/D1bakar/whats_up/compare/v0.1.0...HEAD
[0.1.0]: https://github.com/D1bakar/whats_up/releases/tag/v0.1.0
