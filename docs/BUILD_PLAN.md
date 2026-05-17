# Build Plan — Phase 1 MVP

Ordered, dependency-aware task list. **Work top to bottom.** Each task has acceptance
criteria; a task is "done" only when its criteria pass and `make verify` is green.
Check the box, then append a line to `docs/PROGRESS.md`.

Legend: `[ ]` todo · `[~]` in progress · `[x]` done · `(→Dn)` see DECISIONS.md.

---

## Epic 0 — Scaffolding & dev loop  *(no external deps)*

- [x] **0.1** Repo skeleton: `src/backend/`, `frontend/`, `infra/` per CLAUDE.md
  layout; `pyproject.toml` (uv, ruff, mypy, pytest, FastAPI, SQLAlchemy 2.0,
  Pydantic v2, Alembic); `frontend/` Vite+React+TS app.
- [x] **0.2** `Makefile` single entrypoint: `help`, `install`, `dev`, `verify`
  (lint+typecheck+test), `test`, `fmt`, `lint`, `typecheck`, `migrate`, `seed`,
  `down`, `build-hermes`, `e2e`. *AC met:* `make help` lists all; `make verify`
  green (ruff ✓ mypy ✓ pytest ✓).
- [x] **0.3** `infra/docker-compose.dev.yml`: Postgres + Traefik; `.env.example`
  consumed by `config.py`. *AC:* compose+traefik config validated; `/health`
  returns 200 (test_health). Full `docker compose up` exercised from Epic 2.
- [x] **0.4** CI workflow (`.github/workflows/ci.yml`) runs verify + SPA build on push.
- *AC for Epic 0:* fresh clone → `make dev && make verify` green with zero external
  accounts.

## Epic 1 — Provider abstraction layer  *(→D1)*

- [x] **1.1** 5 provider ABCs + DTOs (`providers/base.py`); factory with
  `(kind,mode)→impl` registry, lazy import so unbuilt epics don't break boot.
- [x] **1.2** Contract-test harness established (parametrized over `mock` +
  skip-if-no-creds `real`); **ConsoleEmail** reference impl + its contract suite
  prove the pattern end-to-end. Per-provider suites land with each epic.
- [x] *AC met:* `tests/test_architecture.py` fails the build if
  stripe/paramiko/supabase/resend/docker is imported outside `providers/`.

## Epic 2 — Data layer

- [x] **2.1** Web-app models (`users` provider+ext_id, `agents`, `subscriptions`,
  `processed_events`) — SQLAlchemy 2.0, selectin relationships.
- [x] **2.2** Fleet schema models (`vps_servers`, `agent_slots`, `vps_ssh_keys`)
  in `fleet` schema; SQLite collapses it via schema_translate_map (zero-dep tests).
  Atomic slot-claim query implemented in Epic 5's LocalPgFleet.
- [x] **2.3** `make seed` — 1 fake VPS + N slots + admin user; idempotent.
- [x] *AC met:* SQLite model/seed tests green; **real-Postgres** Alembic up→down
  round-trip green (test_migrations, runs in CI w/ postgres service); `make
  migrate && make seed` verified against dev Postgres (10 slots + admin).

## Epic 3 — Auth (Supabase Auth abstraction)  *(→D1)*

- [x] **3.1** `MockOAuth` (deterministic, offline) + `SupabaseAuth` (lazy SDK,
  credential-gated) behind `AuthProvider`; contract suite green.
- [x] **3.2** `/api/auth/{login,callback,logout,me}`; JWT session in HttpOnly
  cookie (`security.py`); user upsert on (provider,ext_id); `current_user` /
  `require_admin` deps; open-redirect-safe. DI layer (`dependencies.py`) added.
- [x] *AC met:* `test_auth_flow` drives login→callback→me→logout fully offline;
  forged-state rejected; verify green (15 passed, 5 skipped).

## Epic 4 — Billing (Stripe abstraction)

- [x] **4.1** `FakeBilling` (in-process, mock-pay→same handler) + `StripeBilling`
  (lazy SDK, signature verify) behind `BillingProvider`; contract suite green.
- [x] **4.2** `POST /api/agents/checkout` (auth) creates pending agent + checkout;
  `POST /api/webhooks/stripe` verifies + is idempotent via `processed_events`.
- [x] **4.3** `services/billing.handle_event`: `checkout.session.completed` →
  subscription + agent `paid` (slot/deploy seam for Epic 7);
  `subscription.deleted` → cancel; `invoice.payment_failed` → agent `error`.
- [x] *AC met:* `test_billing_webhook` — checkout→mock-pay→paid end to end;
  re-delivery is a no-op (one subscription); bad signature 400.

## Epic 5 — Fleet & slot pool

- [x] **5.1** `LocalPgFleet` (atomic `UPDATE … WHERE status='available'
  RETURNING`) + `SupabaseFleet` (edge-fn over httpx, gated) behind
  `FleetRegistry`; `services/agent_pool.claim_slot` retry-on-race.
- [x] **5.2** Concurrency test: 2 slots, 5 concurrent claims → exactly 2 win on
  distinct slots, 3 fail, pool drained (no double-assign). Pool-exhausted →
  `SlotUnavailable` (surfaced as 409 by Epic 7).
- [x] *AC met:* contract suite green vs mock; engine cache shared
  (`db.session.get_database_for`). Verify green (25 passed, 8 skipped).

## Epic 6 — Provisioning

- [x] **6.1** `LocalDockerProvisioner` (real Docker SDK, blocking ops off-loop)
  + `SshProvisioner` (paramiko, gated); shared `compose.py` (build_env +
  render_compose); user env can't override reserved contract keys.
- [x] **6.2** `scripts/{deploy-agent,recycle-agent,wipe-data}.sh`; SSH writes a
  chmod-600 `.env` (secrets never in any DB — D12); local injects env directly.
- [x] **6.3** `deploy/stop/start/recycle/status`; deploy failure raises
  `ProviderError` so the orchestrator rolls back the slot (Epic 7 §4.1).
- [x] *AC met:* `test_provisioner` spins a **real container** (stand-in image,
  prod swaps hermes via `HERMES_ADAPTER_IMAGE`), `/health` polled green, recycle
  wipes volumes + removes container; `test_compose` covers rendering offline.

## Epic 7 — Agents API

- [x] **7.1** `checkout`, `GET /agents`, `GET /agents/{id}` (api_key once→null),
  `PATCH` rename, `stop`/`start`, `redeploy` (config upload, secrets not stored),
  `cancel`→recycle. Ownership enforced. `services/provisioning` wires slot-claim
  + deploy into the billing `paid` seam; failure rolls the slot back.
- [x] **7.2** `GET /api/routing/traefik` (HTTP-provider) emits live routes per
  assigned slot from the registry (→ARCHITECTURE §4.3).
- [x] *AC met:* `test_agents_api` drives rent→deploy→detail(once)→rename→
  stop/start→redeploy→cancel→recycle (slot returns to pool) via API; routing
  test green. Verify green (33 passed, 8 skipped).

## Epic 8 — Frontend

- [x] **8.1** Typed API client (`lib/api.ts`), `AuthProvider` + `RequireAuth`
  guard (auto-login redirect), themed `Layout`, `theme.ts` toggle, `bits.tsx`
  (StatusBadge/CopyField). Public `GET /api/fleet/stats` added + tested.
- [x] **8.2** Pages on the bbalaji design tokens: Landing (fleet widget, pricing,
  how-it-works, FAQ), Dashboard, RentAgent, AgentDetail (copy buttons,
  key-shown-once banner, redeploy/stop/start/cancel), Admin (snapshot).
- [x] *AC:* SPA builds + typechecks (tsc strict) clean; it calls exactly the
  endpoints the Epic-7 e2e drives end to end. Browser click-through (Playwright)
  deferred to Epic 11.

## Epic 9 — Email notifications

- [x] **9.1** Shared `email_templates` (subjects+bodies); `ConsoleEmail` (sink)
  + `ResendEmail` (lazy SDK, gated). `services/notifications` maps lifecycle →
  template, best-effort. Wired: welcome (first agent only) + agent_deployed on
  deploy; agent_offline on payment_failed; cancellation_confirmed + agent_recycled
  on cancel; renewal_reminder ready for Epic 11 sweep.
- [x] *AC met:* `test_notifications` asserts each event's template hits the sink
  (incl. no duplicate welcome on 2nd agent). Verify green (36 passed, 8 skipped).

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
