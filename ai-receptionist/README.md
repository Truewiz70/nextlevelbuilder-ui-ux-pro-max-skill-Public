# AI Receptionist Platform

Multi-tenant, voice-first AI receptionist for legal and dental practices.
Answers calls, answers FAQs from a per-tenant knowledge base, qualifies leads,
books appointments, syncs CRM, and sends confirmations — configured per
business, never custom-coded per business.

> **Note:** This directory is designed to become the root of the dedicated
> `ai-receptionist` repository. Until that repo exists it lives inside the
> planning repo; everything under this folder is self-contained.

## Architecture (summary)

- **Voice layer (vendor):** Vapi on Twilio numbers — ASR, TTS, turn-taking.
  Isolated behind a `VoiceProvider` interface; Retell AI is the fallback adapter.
- **Platform (owned):** FastAPI modular monolith — 8 bounded modules
  (`telephony`, `conversation`, `scheduling`, `crm`, `notifications`,
  `tenants`, `analytics`, `escalation`), each replaceable behind a provider
  interface.
- **AI:** Claude API — Sonnet for in-call reasoning, Haiku for classification
  and summaries. Voyage AI for knowledge-base embeddings.
- **Data:** PostgreSQL 16 + pgvector (RLS-enforced multi-tenancy), Redis for
  call state and the post-call job queue.
- **v1 escalation policy:** voicemail-plus-callback (no live transfer).
- **Language:** English only at launch.

Full design documents: `../docs/ai-receptionist/` (Phase 1 architecture,
Phase 2 foundations).

## Prerequisites

- Docker + Docker Compose
- Python 3.12+ (for running the API outside Docker)
- Make

## Quick start

```bash
cp .env.example .env          # then fill in secrets (see Phase 2 doc §4)
make up                       # postgres + redis + api via docker compose
make migrate                  # apply database migrations
curl localhost:8000/healthz   # -> {"status":"ok"}
curl localhost:8000/readyz    # -> {"status":"ready", ...} (checks DB + Redis)
```

Local development without Docker for the API:

```bash
make install                  # creates .venv and installs apps/api
make db                       # starts only postgres + redis in Docker
make migrate
make dev                      # uvicorn with reload on :8000
make test
make lint
```

## Repository layout

```
apps/api/          FastAPI modular monolith (source of truth for the backend)
apps/dashboard/    Next.js dashboard (scaffolded in Phase 7)
config/tenants/    Example tenant configurations (dental, legal)
infra/             Deploy blueprints (Railway/Vercel) — populated in Phase 8
.github/workflows/ CI (activates when this folder becomes the repo root)
```

## Documentation standard

Every module ships a `README.md` covering: purpose, dependencies, inputs,
outputs, configuration, future improvements, and known risks.
