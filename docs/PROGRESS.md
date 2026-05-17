# Progress Log

Append-only state. Newest entry on top. At the start of every session read the
**Status** block, then jump to **Next action**.

---

## Status

- **Phase:** 1 (MVP)
- **Current epic:** Epic 0 — Scaffolding & dev loop (not started)
- **Last updated:** 2026-05-17
- **Local stack:** not yet scaffolded — nothing to run
- **`make verify`:** n/a (no Makefile yet)

## Next action

Begin **BUILD_PLAN 0.1** — create the repo skeleton (`src/backend/`, `frontend/`,
`infra/`, `scripts/`) and `pyproject.toml` / Vite app. Then 0.2 (`Makefile`).

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
