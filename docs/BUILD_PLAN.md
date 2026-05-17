# Build Plan — Phase 1 MVP

Ordered, dependency-aware task list. **Work top to bottom.** Each task has acceptance
criteria; a task is "done" only when its criteria pass and `make verify` is green.
Check the box, then append a line to `docs/PROGRESS.md`.

Legend: `[ ]` todo · `[~]` in progress · `[x]` done · `(→Dn)` see DECISIONS.md.

---

## Epic 0 — Scaffolding & dev loop  *(no external deps)*

- [ ] **0.1** Repo skeleton: `src/backend/`, `frontend/`, `infra/`, `scripts/` per
  CLAUDE.md layout; `pyproject.toml` (ruff, pytest, FastAPI, SQLAlchemy 2.0,
  Pydantic v2, Alembic), `frontend/` Vite+TS app.
- [ ] **0.2** `Makefile` as the single entrypoint: `help`, `dev`, `verify`
  (lint+typecheck+test), `test`, `fmt`, `migrate`, `seed`, `down`. *AC:* `make help`
  lists all; `make verify` runs on empty project and passes.
- [ ] **0.3** `infra/docker-compose.dev.yml`: Postgres + Traefik. `.env.example`
  consumed. *AC:* `make dev` brings the stack up; `/health` returns 200.
- [ ] **0.4** CI workflow running `make verify` on push.
- *AC for Epic 0:* fresh clone → `make dev && make verify` green with zero external
  accounts.

## Epic 1 — Provider abstraction layer  *(→D1)*

- [ ] **1.1** Define the 5 provider interfaces (`fleet`, `billing`, `provisioner`,
  `auth`, `email`) + a registry that selects impl from `*_MODE` env.
- [ ] **1.2** One shared **contract test suite** per provider, parametrized to run
  against both mock and (skipped-if-no-creds) real impls.
- *AC:* importing `stripe`/`paramiko`/`supabase` anywhere outside `providers/`
  fails a lint/architecture test.

## Epic 2 — Data layer

- [ ] **2.1** Web-app models + Alembic migration: `users`, `agents`,
  `subscriptions`, `processed_events` (PRD §5.4 + idempotency table).
- [ ] **2.2** Fleet registry schema (separate Postgres schema for local): `vps_servers`,
  `agent_slots`, `ssh_keys`. Atomic slot-claim query (→ARCHITECTURE §7).
- [ ] **2.3** `make seed`: 1 fake VPS + N available slots; one admin user.
- *AC:* migrations up/down clean; seed produces a rentable pool.

## Epic 3 — Auth (Supabase Auth abstraction)  *(→D1)*

- [ ] **3.1** `MockOAuth` + `SupabaseAuth` behind `AuthProvider`; deterministic
  identity in mock.
- [ ] **3.2** `/auth/login`, `/auth/callback`, session JWT in HttpOnly cookie,
  user upsert, `user`/`admin` roles.
- *AC:* full login→session→logout works offline via mock; contract test green.

## Epic 4 — Billing (Stripe abstraction)

- [ ] **4.1** `FakeBilling` + `StripeBilling` behind `BillingProvider`.
- [ ] **4.2** `/agents/checkout` creates pending agent + checkout; webhook endpoint
  with signature verify + idempotency (`processed_events`).
- [ ] **4.3** Handlers: `checkout.session.completed` → provision;
  `customer.subscription.deleted` / `invoice.payment_failed` → cancel/grace
  (→ARCHITECTURE §4.2).
- *AC:* mock checkout drives the real webhook handler end to end.

## Epic 5 — Fleet & slot pool

- [ ] **5.1** `LocalPgFleet` + `SupabaseFleet` behind `FleetRegistry`:
  `find_available_slot`, `assign`, `unassign`, `get_route`, `slot_status`.
- [ ] **5.2** Pool-exhausted (409) + concurrency-safe assignment test (two
  simultaneous rents get different slots).
- *AC:* contract test green against both impls.

## Epic 6 — Provisioning

- [ ] **6.1** `LocalDockerProvisioner` + `SshProvisioner` behind
  `AgentProvisioner`; render the §5 compose template.
- [ ] **6.2** `scripts/{deploy-agent,recycle-agent,wipe-data}.sh`; user `.env`
  written root-only, never persisted (→D12).
- [ ] **6.3** Lifecycle: `deploy/stop/start/recycle/stats`; failure rolls back the
  slot assignment (→ARCHITECTURE §4.1).
- *AC:* in local mode, deploy spins a real `hermes-adapter` container; `/health` on
  8766 responds; recycle wipes volumes and frees the slot.

## Epic 7 — Agents API

- [ ] **7.1** `POST /agents/checkout`, `GET /agents`, `GET /agents/{id}`
  (api_key shown once → null), `PATCH` (rename), `POST .../stop|start`,
  `POST .../cancel`.
- [ ] **7.2** Dynamic Traefik routing source for `{slot}/(a2a|ws)`
  (→ARCHITECTURE §4.3).
- *AC:* rent→deploy→detail→cancel→recycle works end to end via API in local mode.

## Epic 8 — Frontend

- [ ] **8.1** API client + auth guard.
- [ ] **8.2** Pages: Landing (incl. fleet-availability widget), Auth redirect,
  Dashboard, RentAgent, AgentDetail (copy buttons, key-shown-once), Admin.
- *AC:* clicking through the browser performs a full rent in local mode.

## Epic 9 — Email notifications

- [ ] **9.1** `ConsoleEmail` + `ResendEmail`; templates: welcome, agent_deployed,
  renewal_reminder(3d), cancellation_confirmed, agent_recycled, agent_offline.
- *AC:* each lifecycle event emits the right template to the sink; assertable.

## Epic 10 — Admin panel

- [ ] **10.1** System overview (slots total/available/assigned/error), per-VPS
  health, per-agent table, force stop/restart/wipe/recycle, users list.
- *AC:* admin-only; can recycle any agent.

## Epic 11 — Hardening & E2E

- [ ] **11.1** End-to-end local happy-path test (anon→login→rent→deploy→connect
  stub→cancel→recycle) in CI.
- [ ] **11.2** Consistency sweep (orphan slot/agent), renewal/grace scheduled job,
  rate limiting, input validation.
- [ ] **11.3** `README.md` quickstart; fill ToS placeholders if user provided them.
- *AC:* `make verify` + E2E green from a clean clone with zero external accounts.

---

## Out of scope for Phase 1 (PRD §6)

Hermes Studio, hosting Akela AI, price tiers, non-Stripe payment, mobile, usage
analytics, team sharing. Do not build these without an explicit decision.

## Graduation to real services (post-MVP, needs user)

Per concern: set `*_MODE=real`, supply credentials, run that provider's contract
test against the real impl. No application code changes — that's the test of whether
the abstraction held.
