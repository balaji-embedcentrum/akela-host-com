# Progress Log

Append-only state. Newest entry on top. At the start of every session read the
**Status** block, then jump to **Next action**.

---

## Status

- **Phase:** 1 (MVP)
- **Current epic:** Epic 4 — Billing (next)
- **Last updated:** 2026-05-17
- **Local stack:** backend boots; SPA builds; data layer (PG-verified); auth done
  (offline login flow); DI layer in place
- **`make verify`:** green — ruff ✓ mypy ✓ pytest ✓ (15 passed, 5 skipped)

## Next action

Begin **Epic 4** — `FakeBilling` + `StripeBilling` behind `BillingProvider`;
`/api/agents/checkout` + webhook endpoint (signature verify + idempotency); event
handlers wired to provisioning (provisioning lands Epic 6). Then Epic 5 (fleet).

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
