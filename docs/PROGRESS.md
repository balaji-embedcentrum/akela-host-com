# Progress Log

Append-only state. Newest entry on top. At the start of every session read the
**Status** block, then jump to **Next action**.

---

## Status

- **Phase:** 1 (MVP)
- **Current epic:** Epic 11 — Hardening & E2E (final)
- **Last updated:** 2026-05-17
- **Local stack:** backend + SPA + emails + admin complete
- **`make verify`:** green — ruff ✓ mypy ✓ pytest ✓ (39 passed, 8 skipped); SPA
  build ✓

## Next action

Begin **Epic 11** — renewal/grace + recycle scheduled sweep, rate limiting on
auth+rent, orphan consistency check, full E2E happy-path test, README quickstart,
fill ToS placeholders if provided. Then Phase 1 MVP is done.

## Needs user (not code-blocking)

- Real Supabase / Stripe / GitHub+Google OAuth / VPS SSH credentials — only when a
  concern graduates from `mock` to `real` (post-MVP). Dev needs none.
- ToS placeholders in `docs/terms-of-service.md`: `[DATE]`,
  `[YOUR JURISDICTION]`, `[YOUR EMAIL]` (→D11). Needed before real payments.
- Confirm `hermes-adapter:latest` image is built/available locally for Epic 6
  (or we add a `make build-hermes` that builds it from the local repo).

## Open / watch

- D7, D8, D9, D10, D11 are provisional (⏳) — revisit before launch.
- hermes-adapter has a built-in fleet mode (D8) — evaluate reuse after MVP.

---

## Log

### 2026-05-17 — Epic 10 complete (admin panel)
- `routers/admin.py` (router-level `require_admin`): overview, per-VPS rollup,
  all-agents (w/ owner), users (w/ counts), force stop/start/restart/wipe/recycle
  on any agent. SPA Admin expanded (cards + agents/users tables + actions).
- `test_admin`: non-admin 403; admin overview/agents/users/vps; force-recycle
  any agent frees the slot. Verified: ruff ✓ mypy ✓ pytest ✓ (39 passed, 8
  skipped); SPA build ✓. **Next:** Epic 11.

### 2026-05-17 — Epic 9 complete (email notifications)
- `email_templates` (shared subjects/bodies, safe render); `email_console`
  refactored to it; `email_resend` real impl (lazy SDK, gated).
- `services/notifications` (best-effort) wired: welcome (first agent only) +
  agent_deployed on deploy; agent_offline on payment_failed; cancellation +
  agent_recycled on cancel. `_finalize` extended for payment_failed email.
- `test_notifications` asserts templates hit the sink incl. single welcome.
- Verified: ruff ✓ mypy ✓ pytest ✓ (36 passed, 8 skipped). **Next:** Epic 10.

### 2026-05-17 — Epic 8 complete (frontend SPA)
- Typed `lib/api.ts`, `AuthProvider`/`RequireAuth`, `Layout`, theme toggle,
  `StatusBadge`/`CopyField`. Public `GET /api/fleet/stats` (+ test).
- Pages on bbalaji tokens: Landing (fleet widget/pricing/FAQ), Dashboard,
  RentAgent, AgentDetail (copy buttons, key-once banner, redeploy/lifecycle),
  Admin snapshot. Routed + guarded; admin route role-gated.
- SPA `npm run build` + strict `tsc` clean; backend 34 passed, 8 skipped.
- **Next:** Epic 9.

### 2026-05-17 — Epic 7 complete (agents API + orchestration + routing)
- `services/provisioning` (provision_paid_agent / recycle_agent) wired into the
  billing webhook's `paid` seam; slot rollback on failure.
- `routers/agents.py`: checkout/list/detail(api_key once)/rename/stop/start/
  redeploy(config, secrets unstored)/cancel→recycle, ownership-enforced.
  `routers/routing.py`: Traefik HTTP-provider endpoint.
- Fix: commit billing state before provisioning (durable de-dup + releases the
  SQLite single-writer lock so the fleet connection can claim); SQLite WAL +
  busy_timeout. Updated Epic-4 tests to the now-integrated `deployed` outcome.
- `FakeProvisioner` test double (no Docker) for API/e2e; harness seeds the pool.
- Verified: ruff ✓ mypy ✓ pytest ✓ (33 passed, 8 skipped). **Next:** Epic 8.

### 2026-05-17 — Epic 6 complete (provisioning)
- `compose.py` (build_env w/ reserved-key guard + render_compose) shared by both
  provisioners. `LocalDockerProvisioner` (real Docker SDK, off-loop blocking
  ops, health poll), `SshProvisioner` (paramiko, gated). Lifecycle scripts.
- Stand-in test image (`infra/test-agent`) emulates the hermes contract; real
  container deploy→health→stop/start→recycle→wipe verified; offline render tests.
- Verified: ruff ✓ mypy ✓ pytest ✓ (29 passed, 8 skipped). **Next:** Epic 7.

### 2026-05-17 — Epic 5 complete (fleet & slot pool)
- `LocalPgFleet` (atomic claim via UPDATE…RETURNING) + `SupabaseFleet` (edge-fn,
  httpx, gated). `services/agent_pool.claim_slot` retries on lost race.
- `db.session.get_database_for` lru_cache shares one engine across DI + providers
  (dependencies refactored to use it).
- Concurrency test: 2 slots / 5 racers → exactly 2 distinct winners, pool drained.
- Verified: ruff ✓ mypy ✓ pytest ✓ (25 passed, 8 skipped). **Next:** Epic 6.

### 2026-05-17 — Epic 4 complete (billing)
- `FakeBilling` (mock-pay → same handler) + `StripeBilling` (lazy SDK, sig verify).
- `routers/agents.py` `POST /checkout`; `routers/webhooks.py` stripe webhook +
  mock-pay shim → one idempotent `services/billing.handle_event` (D13).
- checkout→paid flow, idempotent re-delivery, bad-sig 400, payment_failed→error.
- Slot/deploy left as a documented seam for Epic 7 (agent → `paid`).
- Verified: ruff ✓ mypy ✓ pytest ✓ (22 passed, 7 skipped). **Next:** Epic 5.

### 2026-05-17 — Epic 3 complete (auth)
- `security.py` (JWT session + OAuth state + bcrypt api-key helpers);
  `MockOAuth` (offline, deterministic) + `SupabaseAuth` (lazy SDK).
- `dependencies.py` DI: settings/db/providers/current_user/require_admin —
  test-overridable (sqlite + mock). `routers/auth.py`: login/callback/logout/me,
  HttpOnly cookie, user upsert, open-redirect guard.
- `harness` test fixture (wired app over sqlite+mock). Offline login→session→
  logout flow + forged-state test green.
- Verified: ruff ✓ mypy ✓ pytest ✓ (15 passed, 5 skipped). **Next:** Epic 4.

### 2026-05-17 — Epic 2 complete (data layer)
- Web models (users/agents/subscriptions/processed_events) + fleet models
  (vps_servers/agent_slots/vps_ssh_keys, `fleet` schema). `Database` helper:
  one engine, SQLite collapses `fleet` via schema_translate_map → zero-dep tests.
- Alembic (async env) + initial migration via metadata.create_all (zero drift).
  `make seed` (idempotent: 1 VPS + N slots + admin). SQLite tests + **real PG
  round-trip** green.
- Fixes: env.py `engine.begin()` (was `connect()` → DDL never committed);
  Makefile CLI targets use `PYTHONPATH=src` (project not pip-installed);
  `lazy="selectin"` on relationships (async MissingGreenlet); CI gains a
  postgres service for the migration test.
- Verified: ruff ✓ mypy ✓ pytest ✓ (10 passed, 3 skipped). **Next:** Epic 3.

### 2026-05-17 — Epic 1 complete (provider abstraction layer)
- `providers/base.py`: 5 ABCs (Fleet/Billing/Provisioner/Auth/Email) + DTOs +
  error hierarchy. `providers/factory.py`: `(kind,mode)→impl` registry, lazy
  import, `build_provider`/`build_providers`.
- `ConsoleEmail` mock impl (reference) + parametrized contract suite (mock + real
  skipped w/o creds). `test_architecture.py` guards external-SDK imports.
- main.lifespan tolerates unbuilt impls (boots with providers=None).
- Verified: ruff ✓ mypy ✓ pytest ✓ (5 passed, 3 skipped). **Next:** Epic 2.

### 2026-05-17 — Epic 0 complete (scaffolding & dev loop)
- pyproject (uv, py3.12), `src/backend/` package (config, FastAPI app factory with
  lazy router/provider wiring, `/health`), Makefile (single entrypoint), infra
  compose (Postgres+Traefik) + traefik static/dynamic config, CI workflow.
- `frontend/` Vite+React+TS SPA; **theme extracted from bbalaji-site** into
  `theme.css` (verbatim tokens + app primitives: forms, tables, badges, cred blocks);
  themed shell + dark-mode toggle. SPA builds clean.
- Verified: ruff ✓ mypy ✓ pytest ✓ (1); compose+traefik config valid; SPA build ✓.
- **Next:** Epic 1.

### 2026-05-17 — Commit policy set; planning scaffolding committed to `main`
- User directive: no Co-Authored-By trailer (user creds only); commit + push to `main`
  proactively so nothing is lost on local disk. Recorded as **D14**; CLAUDE.md updated.
- Added `.gitignore` (`.DS_Store`, `.env`, secret/build dirs).
- Committed + pushed the planning artifacts (CLAUDE.md, docs/*, .env.example, .gitignore)
  to `origin/main`. Unrelated untracked dirs (`.github/`, `.vscode/`, `sylang-help/`)
  left untracked pending user confirmation.
- **Next:** unchanged — Epic 0.1.

### 2026-05-17 — Project planning scaffolding created
- Reset local `main` to `origin/main` (`6941dd7`); read PRD + ToS in full.
- Explored local `hermes-agent` / `hermes-adapter`; derived the per-slot container
  contract (one adapter container, ports 8766/9000, `API_SERVER_KEY` auth,
  `/workspaces` + `/opt/data` volumes). Recorded discrepancies vs PRD.
- Decided (with user): local-first build, all externals mocked; provision via local
  Docker; derive compose from the local hermes repos.
- Authored: `CLAUDE.md`, `docs/ARCHITECTURE.md`, `docs/BUILD_PLAN.md`,
  `docs/DECISIONS.md` (D1–D13), `docs/PROGRESS.md`, `.env.example`.
- **Next:** Epic 0.1.
