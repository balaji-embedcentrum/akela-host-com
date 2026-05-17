# CLAUDE.md — akela-host.com

> Auto-loaded every session. This is the operating manual for building and running this
> project independently. Read it first, then `docs/PROGRESS.md` to see where we are.

## What this is

A multi-tenant SaaS that **rents persistent Hermes AI agents at $4/month** (prorated,
per-agent via Stripe). Users rent an agent here, get connection credentials, and plug them
into their *own self-hosted Akela AI* control plane.

- **akela-host.com** (this repo) = rent & host agents. We own the infra.
- **akela-ai.com** = free, user-self-hosted UI to *use* the agents. Not in this repo.

Authoritative product spec: `docs/PRD.md`. This file is the *how*; the PRD is the *what*.

## Current state

Docs-only repo building toward **Phase 1 MVP**. No application code exists yet.
The build is executed task-by-task from `docs/BUILD_PLAN.md`.

## The three non-obvious things

1. **Two databases, federated by convention, not FK.**
   - *Fleet registry* (conceptually Supabase): `vps_servers`, `agent_slots`, SSH keys.
   - *Web-app DB* (Postgres): `users`, `agents`, `subscriptions`.
   - `agents.slot_name` ↔ `agent_slots.slot_name` is a **logical** link across DBs — no
     enforced foreign key. Never assume a cross-DB join.

2. **Secrets are never persisted. Anywhere.**
   - User uploads their own `.env`; it is pushed to the agent host and embedded in the
     container at deploy time. It is **never** written to either DB or to Supabase.
   - Only stored: `agent_api_key_hash` (bcrypt) + non-secret config (display name).
   - The plaintext agent API key is shown to the user **exactly once** after deploy.

3. **Pre-spawned slots, not on-demand containers.**
   - Each agent host has a fixed pool of slots (PRD: 250). Renting = *assigning* an
     existing slot. Cancelling = *recycling* it back to the pool. Slots are never created
     or destroyed at runtime.

## Local-first mandate (how we run with zero external accounts)

Decided with the user: **build everything runnable locally with all external services
mocked.** This is non-negotiable for independent operation — no task may hard-depend on a
real Supabase/Stripe/VPS/OAuth account.

Every external dependency sits behind a **provider interface** with two implementations:

| Concern        | Real impl (later)        | Mock/local impl (now)                          |
|----------------|--------------------------|------------------------------------------------|
| Fleet registry | Supabase (Edge Fns)      | Local Postgres schema + FastAPI routes         |
| Billing        | Stripe Subscriptions     | In-process fake Stripe + replayable webhooks   |
| Provisioning   | SSH (paramiko) → VPS     | `LocalDockerProvisioner` (local Docker engine) |
| Auth           | Supabase Auth (OAuth)    | Mock OAuth provider returning a fixed identity |
| Email          | Resend / SMTP            | Console/file sink                              |

Which impl loads is chosen by env vars (`*_MODE=mock|real`) — see `.env.example`.
**Rule:** if you write code that calls Stripe/Supabase/SSH/OAuth directly instead of
through its provider interface, that's a bug.

## The hermes contract (the thing we provision)

Derived by reading the local `hermes-agent` / `hermes-adapter` repos. See
`docs/ARCHITECTURE.md` §"Hermes per-slot contract" for the full compose template.

- **One container per slot.** `hermes-adapter`'s Dockerfile is
  `FROM nousresearch/hermes-agent:latest` — the agent is embedded. We deploy the adapter
  image only; we do **not** run a separate hermes-agent container.
- **Ports:** workspace API `8766` (env `HERMES_ADAPTER_PORT`), A2A `9000`
  (env `A2A_PORT`). The adapter Dockerfile sets `9001` but the code/compose default is
  `9000` — use **9000**.
- **Inbound auth:** bearer token via `API_SERVER_KEY` (checked first) or `A2A_KEY`.
  This *is* the PRD's `AKELA_API_KEY`. Public unauthenticated paths:
  `/.well-known/agent.json`, `/health`.
- **Persistence:** `/workspaces` (git repos) + `/opt/data` (`HERMES_HOME`:
  sessions, memories, skills). Per-slot host volumes map into these.
- **Canonical sources:** `/Users/balajiboominathan/Documents/hermes-agent` and
  `/Users/balajiboominathan/Documents/hermes-adapter`. Ignore
  `hermes-agent/a2a_adapter/` — it's an empty stub.

## Tech stack

- **Backend:** Python 3.12, FastAPI, SQLAlchemy 2.0, Pydantic v2, Alembic, pytest, ruff.
- **Frontend:** React 18 + TypeScript + Vite (SPA, served static).
- **Infra (dev):** Docker Compose — Postgres, Traefik, the local agent host.
- **Provisioning:** paramiko (real) / local Docker SDK (mock).

## Target directory layout

```
akela-host-com/
├── CLAUDE.md                  ← this file
├── .env.example
├── Makefile                   ← single entrypoint for every command
├── docs/{PRD,ARCHITECTURE,BUILD_PLAN,DECISIONS,PROGRESS}.md
│   └── terms-of-service.md
├── src/backend/               # FastAPI app (see ARCHITECTURE.md for module map)
├── frontend/                  # React SPA
├── infra/                     # docker-compose.dev.yml, traefik/
└── scripts/                   # deploy-agent / recycle-agent / wipe-data
```

## Commands

Once Epic 0 lands, **every** action goes through the `Makefile` (`make help`).
Until then there is nothing to run. Never invent ad-hoc commands — add a make target.

## Conventions

- Backend: ruff-formatted, type-hinted, Pydantic v2 schemas, SQLAlchemy 2.0 style,
  async FastAPI routes, dependency-injected provider interfaces. Tests with pytest;
  every provider has a contract test that runs against *both* impls.
- Frontend: TypeScript strict, function components, the API client is the only place
  that talks to the backend.
- Commits: conventional commits. **No Co-Authored-By / "Generated with" trailer** — commits
  are authored under the user's git credentials only (user directive, overrides defaults).
- **Commit and push to `main` regularly and proactively** — after each completed BUILD_PLAN
  task or meaningful chunk — so no work is lost on local disk. Work directly on `main`
  (no feature branch unless the user asks). Never commit secrets (`.env`, keys). See D14.

## How to run a session independently

1. Read `docs/PROGRESS.md` → find the **Next action**.
2. Open `docs/BUILD_PLAN.md` → take the first unchecked task in the current epic.
3. Check `docs/DECISIONS.md` before making any architectural choice — don't re-litigate.
4. Implement. Write/extend tests. Keep the local stack runnable (`make verify` green).
5. Update `docs/BUILD_PLAN.md` (check the box) and **append** to `docs/PROGRESS.md`
   (what changed, what's next, anything that became blocked).
6. Surface to the user only what genuinely needs them (real credentials, ToS legal
   fields, product decisions). Everything else: keep going.

## What still needs the user (not code-blocking)

Tracked in `docs/PROGRESS.md` → "Needs user". Includes: real Supabase/Stripe/OAuth/VPS
credentials when we graduate off mock; ToS placeholders (`[DATE]`,
`[YOUR JURISDICTION]`, `[YOUR EMAIL]`). None of these block local-first development.
