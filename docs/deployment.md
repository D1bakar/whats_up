# Deployment Guide

This document describes how to deploy WhatsApp Platform using the **existing Docker Compose architecture**. There is no cloud-specific deployment target configured in the repository yet.

## Prerequisites

| Requirement | Notes |
|-------------|--------|
| Linux VM or container host | With Docker Engine and Docker Compose v2 |
| PostgreSQL 16 | Provided by Compose or managed service |
| Redis 7 | Provided by Compose or managed service |
| Public HTTPS endpoint | Required for Meta WhatsApp webhooks |
| Secrets store | Platform secrets manager or host env — never commit `.env` |

## Environment separation

| Environment | `ENVIRONMENT` | Typical use |
|-------------|---------------|-------------|
| Development | `development` | Local `docker-compose.dev.yml`, mock providers |
| Staging | `staging` | Pre-production Meta test app |
| Production | `production` | Live WhatsApp Business number |

Production must set:

```env
ENVIRONMENT=production
DEBUG=false
WHATSAPP_PROVIDER=meta
AI_PROVIDER=openai
WHATSAPP_APP_SECRET=<required>
META_WHATSAPP_ACCESS_TOKEN=<required>
META_WHATSAPP_PHONE_NUMBER_ID=<required>
OPENAI_API_KEY=<required when AI_PROVIDER=openai>
SECRET_KEY=<strong random value>
DATABASE_URL=<production postgres URL>
REDIS_URL=<production redis URL>
```

The application uses Pydantic Settings validation. Missing production credentials for Meta or OpenAI cause provider failures at runtime; webhook signature validation is enforced when `WHATSAPP_APP_SECRET` is set.

## Docker Compose deployment (recommended path)

1. Clone the repository on the target host.
2. Copy `.env.example` to `.env` and fill production values externally.
3. From the repository root:

```bash
docker compose -f docker/docker-compose.yml up -d --build
```

4. Run migrations (once per release):

```bash
docker compose -f docker/docker-compose.yml exec api alembic upgrade head
```

5. Verify:

```bash
curl -f http://localhost:8000/health
curl -f http://localhost:8000/ready
```

`/ready` returns `503` when PostgreSQL or Redis is unreachable.

## Container images (CI/CD)

GitHub Actions CI builds backend and frontend images on every push to `master`.

The optional **CD workflow** (`.github/workflows/cd.yml`) can publish images to GitHub Container Registry (GHCR) when manually triggered. Image tags match the commit SHA.

Pull on the deployment host:

```bash
docker pull ghcr.io/d1bakar/whats_up-api:<sha>
docker pull ghcr.io/d1bakar/whats_up-frontend:<sha>
```

Adjust the registry path to match your GitHub org/user.

## GitHub Actions secrets (production environment)

Configure these in **Settings → Environments → production** (do not commit values):

| Secret | Purpose |
|--------|---------|
| `DATABASE_URL` | Production PostgreSQL connection string |
| `REDIS_URL` | Production Redis connection string |
| `SECRET_KEY` | Application secret key |
| `WHATSAPP_VERIFY_TOKEN` | Meta webhook verification token |
| `WHATSAPP_APP_SECRET` | Meta webhook HMAC secret |
| `META_WHATSAPP_ACCESS_TOKEN` | Meta Graph API token |
| `META_WHATSAPP_PHONE_NUMBER_ID` | Meta phone number ID |
| `OPENAI_API_KEY` | OpenAI API key (if `AI_PROVIDER=openai`) |
| `DEPLOY_HOST` | Optional — SSH host for remote deploy |
| `DEPLOY_SSH_KEY` | Optional — private key for remote deploy |
| `DEPLOY_USER` | Optional — SSH user |

Optional remote deploy runs only when `DEPLOY_HOST` is configured.

## Post-deploy smoke test

1. `GET /health` → `200`, `"status": "ok"`
2. `GET /ready` → `200`, PostgreSQL and Redis checks `"ok"`
3. Meta webhook verification (`GET /webhooks/whatsapp`) with correct verify token
4. Send `/start` to the bot — deterministic response, no AI call required
5. Send natural-language text — AI orchestration (when enabled)

## Not configured in this repository

- Kubernetes / ECS / Railway / Fly.io manifests
- Terraform or cloud provisioning
- Automatic DNS / TLS certificate management
- Managed database provisioning

These require external account setup before a public production URL exists.
