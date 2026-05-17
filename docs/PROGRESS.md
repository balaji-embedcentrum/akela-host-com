# Progress Log

Append-only state. Newest entry on top. At the start of every session read the
**Status** block, then jump to **Next action**.

---

## Status

- **Phase:** 1 (MVP)
- **Current epic:** Epic 1 — Provider abstraction layer (next)
- **Last updated:** 2026-05-17
- **Local stack:** backend boots (FastAPI `/health` 200), SPA builds; Postgres+Traefik
  compose validated
- **`make verify`:** green — ruff ✓ mypy ✓ pytest ✓ (1 test)

## Next action

Begin **Epic 1** — define the 5 provider interfaces + factory + per-provider contract
test suite (1.1, 1.2). Then Epic 2 (data layer).

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
