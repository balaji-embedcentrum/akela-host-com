# akela-host.com

Multi-tenant SaaS that **rents persistent Hermes AI agents for $4/month**. Users rent
an agent here, get connection credentials (A2A URL, Workspace URL, API key), and plug
them into their own self-hosted [Akela AI](https://akela-ai.com). We own the infra; Akela
AI is the free user-managed control plane.

> **Local-first:** the entire stack runs with **zero external accounts**. Supabase,
> Stripe, OAuth, the agent VPS and email are all mocked behind provider interfaces and
> selected by `*_MODE` env vars. Swap in real credentials later — config, not code.

See `docs/PRD.md` (what), `docs/ARCHITECTURE.md` (how), `docs/BUILD_PLAN.md` (status),
`docs/DECISIONS.md` (why), `CLAUDE.md` (operating manual).

## Prerequisites

- [`uv`](https://docs.astral.sh/uv/) (manages Python 3.12), Node 20+, Docker (running).
- Nothing else — no Postgres/Supabase/Stripe/VPS needed for development.

## Quickstart

```bash
make install            # venv (py3.12) + backend deps + frontend deps
make verify             # lint + typecheck + full test suite (mock mode)
make e2e                # the end-to-end happy-path test
```

Run the app locally (mock mode, two terminals):

```bash
make dev                # Postgres + Traefik via docker compose
make migrate            # apply Alembic migrations (web DB + fleet schema)
make seed               # 1 fake VPS + N available slots + an admin user
make api                # FastAPI on :8000
make web                # React SPA on :5173  (open this)
```

`make help` lists every target. The SPA proxies `/api` → the backend so the session
cookie is same-origin. Sign in with the dev mock provider, rent an agent, and the
mock-pay shim drives the real provisioning + webhook path end to end.

> The per-slot agent runs the **hermes-adapter** image. Tests use a tiny stand-in
> image; for a real agent build it from the local repo: `make build-hermes`.

## How it's wired

| Concern | Mock (default) | Real (`*_MODE=real`) |
|---|---|---|
| Fleet registry | local Postgres `fleet` schema | Supabase Edge Functions |
| Billing | in-process fake + mock-pay | Stripe Subscriptions |
| Provisioning | local Docker | SSH (paramiko) → agent VPS |
| Auth | deterministic mock OAuth | Supabase Auth (GitHub/Google) |
| Email | console + `.dev/` JSONL sink | Resend |

Architecture rule: routers/services never import an external SDK directly — only
`backend/providers/` does (enforced by `tests/test_architecture.py`).

## Testing

`make verify` = ruff + mypy + pytest, all in mock mode with no external accounts. A
Postgres-only Alembic round-trip and the real-Docker provisioner test run when their
environment is available (and in CI), and skip cleanly otherwise. Every provider has a
contract suite that runs against the mock and (credentials permitting) the real impl.

## Going to production

Per concern: set its `*_MODE=real`, supply the credentials in `.env` (see
`.env.example`), and run that provider's contract test against the real impl. No
application code changes — that's the test of whether the abstraction held.

**Before taking real payments:** fill the Terms of Service placeholders in
`docs/terms-of-service.md` (`[DATE]`, `[YOUR JURISDICTION]`, `[YOUR EMAIL]`) and have
them reviewed by a lawyer.
