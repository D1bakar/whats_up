# Contributing

Thank you for contributing to WhatsApp Platform. This document describes how to work in the repository effectively and safely.

## Development setup

1. Fork or clone the repository.
2. Copy `.env.example` to `.env` and adjust for local services.
3. Start Postgres and Redis (`docker compose -f docker/docker-compose.dev.yml up -d postgres redis`).
4. Install backend dependencies: `cd backend && uv sync --extra dev`.
5. Run migrations: `uv run alembic upgrade head`.
6. Install frontend dependencies: `cd frontend && npm install`.

## Code quality requirements

All backend changes must pass:

```bash
cd backend
uv run ruff check app tests
uv run ruff format --check app tests
uv run mypy app
uv run pytest
```

Frontend changes must pass:

```bash
cd frontend
npm run lint
npm run typecheck
npm run build
```

Fix root causes instead of weakening tests or lint rules.

## Testing requirements

- Add or update tests for behavior changes.
- Use the mock WhatsApp provider in tests — do not call Meta APIs from CI or local unit tests.
- Tests use isolated SQLite in-memory databases per test function; integration tests against Postgres run in CI.

## Branch conventions

- `main` or `master` — stable integration branch
- `feature/<short-description>` — new functionality
- `fix/<short-description>` — bug fixes
- `chore/<short-description>` — tooling, docs, CI

Keep branches focused on one logical change where possible.

## Commit conventions

Use [Conventional Commits](https://www.conventionalcommits.org/):

```
feat(bot): add order collection state handler
fix(webhook): reprocess events after failed processing
chore(ci): cache uv lockfile in GitHub Actions
docs: update architecture diagram for bot engine
test: add duplicate message idempotency coverage
```

Avoid vague messages such as "update", "fix stuff", or "changes".

## Pull request expectations

- Describe **what** changed and **why**.
- List tests run locally.
- Note any migration or environment variable changes.
- Ensure CI passes.
- Keep PRs reviewable — split large changes when practical.

## Security expectations

- **Never commit** `.env`, tokens, API keys, private keys, or database dumps.
- Use `.env.example` for documented placeholders only.
- Do not log secrets in application code or tests.
- Review diffs for accidental credential exposure before pushing.

See [SECURITY.md](SECURITY.md) for vulnerability reporting.

## Architecture guidance

- Follow the layer boundaries documented in `docs/architecture.md`.
- Webhook handlers stay thin; put business logic in application services.
- Bot engine code must not depend on raw Meta HTTP types in handlers.
- Idempotency must remain database-backed at webhook and message boundaries.

## Questions

Open a GitHub issue for design questions or bug reports. For security issues, follow SECURITY.md instead of filing a public issue.
