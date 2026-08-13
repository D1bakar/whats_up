# Production Readiness Checklist

This document tracks what is **done** vs **required** before treating WhatsApp Platform as an industry-ready production product.

## Current state (v0.1.0)

| Capability | Status |
|------------|--------|
| FastAPI application foundation | Done |
| WhatsApp webhook + mock provider | Done |
| Deterministic bot engine | Done |
| PostgreSQL persistence + migrations | Done |
| Idempotency (webhook + message) | Done |
| AI layer (provider abstraction, orchestrator, mock provider) | Done |
| CI pipeline (lint, test, build) | Done |
| Docker Compose local stack | Done |
| MIT license + contributor docs | Done |

## Required for production launch

### P0 — Blocks real-world deployment

- [ ] **Meta production credentials** — System User token, phone number ID, webhook verify token, app secret
- [ ] **Webhook signature validation enforced** in production (`WHATSAPP_APP_SECRET`)
- [ ] **Secrets management** — no `.env` in production; use vault / platform secrets
- [ ] **HTTPS termination** — public webhook URL with valid TLS
- [ ] **Database backups** — automated PostgreSQL backup and restore tested
- [ ] **Health/readiness probes** wired in orchestrator (K8s/ECS/Railway/etc.)

### P1 — Required for a credible product

- [ ] **Admin authentication** — JWT or session auth for operator API
- [ ] **Admin read API** — conversations, messages, contacts (paginated)
- [ ] **Rate limiting** — webhook and outbound per phone number
- [ ] **Structured observability** — request IDs, metrics, error alerting
- [ ] **Background worker** — decouple webhook ACK from heavy processing (Redis queue)
- [ ] **Staging environment** — separate Meta app / phone number for staging
- [ ] **Runbooks** — incident response, token rotation, Meta webhook failures

### P2 — Product maturity

- [ ] **Admin dashboard UI** — inbox, conversation view, message history
- [ ] **AI / LLM integration** — OpenAI cloud adapter *(done)*; Ollama local adapter *(done)*; production keys as needed
- [ ] **Multi-tenant business accounts** — proper WABA / phone number onboarding
- [ ] **Outbound message audit table** — dedicated `outbound_messages` entity per architecture
- [ ] **Branch protection + required CI** on `main`/`master`
- [ ] **Semantic versioning + CHANGELOG** releases
- [ ] **Dependabot / security scanning** enabled

## Languages & stack

| Language / tech | Where used |
|-----------------|------------|
| **Python** | Backend API, bot engine, migrations, tests |
| **TypeScript** | Next.js admin frontend |
| **JavaScript** | Frontend tooling config |
| **CSS** | Frontend styles |
| **Dockerfile** | API and frontend container images |
| **Shell** | Dev helper scripts |
| **SQL** | Alembic migrations (PostgreSQL) |
| **YAML** | GitHub Actions, Docker Compose |

## Tracking

Production tasks are tracked as GitHub issues labeled `production`. See the [Issues](https://github.com/D1bakar/whats_up/issues) tab.
