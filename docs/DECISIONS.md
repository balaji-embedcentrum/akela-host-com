# Decisions Log (ADR)

Append-only. Each entry: decision, why, status. If a decision is reversed, add a new
entry that supersedes the old one — don't edit history. Referenced as `Dn` elsewhere.

Status: ✅ active · 🔁 superseded · ⏳ provisional (revisit before launch)

---

### D1 — Local-first with provider abstraction ✅
All external systems (Supabase, Stripe, SSH/VPS, OAuth, email) sit behind provider
interfaces with a mock and a real impl, selected by `*_MODE` env.
**Why:** user requires the project to run independently with zero external accounts;
a strict boundary keeps mocks honest (shared contract tests) and makes graduating to
real services a config flip, not a rewrite.

### D2 — Supabase simulated as a local Postgres schema ✅
The fleet registry tables live in a separate schema of the same dev Postgres;
"edge functions" are internal FastAPI routes in mock mode.
**Why:** no Supabase account needed for dev; same SQL/contract as real Supabase so
`SupabaseFleet` is a thin swap later.

### D3 — Provisioning abstracted; `LocalDockerProvisioner` for dev ✅
Dev provisions real local Docker containers via the Docker SDK; prod uses
`SshProvisioner` (paramiko) to a remote host. Same compose template both ways.
**Why:** exercises the real deploy/recycle logic and a real hermes container
locally, without a VPS.

### D4 — One container per slot (adapter image embeds the agent) ✅
We deploy only the `hermes-adapter` image. Its Dockerfile is
`FROM nousresearch/hermes-agent:latest`, so the agent is bundled.
**Why:** verified by reading the repos; running a second hermes-agent container
would be redundant. Supersedes PRD's two-container description.

### D5 — A2A port is 9000 ✅
Use `A2A_PORT=9000`. The adapter Dockerfile sets `9001` but `config.py` and
`docker-compose.yml` default to `9000`.
**Why:** code/compose is the source of truth; Dockerfile value is vestigial.
Resolves PRD discrepancy.

### D6 — Agent inbound auth via `API_SERVER_KEY` ✅
The agent API key we generate is injected as `API_SERVER_KEY` (the adapter checks it
before `A2A_KEY`). This is the PRD's `AKELA_API_KEY`.
**Why:** matches the adapter's auth precedence; Google token paths are out of scope
for MVP.

### D7 — User `.env` passed through verbatim; keys not validated ✅
The PRD's allowed-vars list names `ANTHROPIC_API_KEY`, but hermes routes LLMs via
`OPENROUTER_API_KEY` / `GOOGLE_API_KEY` / `HF_TOKEN` etc. We inject the user's
uploaded `.env` as-is and do **not** validate, rename, or allowlist keys in MVP.
**Why:** the agent — not us — owns provider routing; an allowlist would break valid
configs and create a maintenance treadmill. Revisit if abuse surfaces. ⏳

### D8 — MVP wraps slots with our own compose; reuse of hermes-adapter fleet mode deferred ⏳
hermes-adapter already ships a fleet/manifest mode (`FLEET_ROOT`,
`HERMES_FLEET_MODE`, `agents.yaml`, `hermes-adapter compose generate`). For MVP we
render our own per-slot compose (one container/slot) rather than adopt it.
**Why:** our model (pre-spawned fixed pool, per-slot isolation, our registry as
source of truth) is simpler to reason about and matches the PRD; adopting the
built-in fleet mode is an optimization to evaluate post-MVP, not a prerequisite.

### D9 — SSH key storage: encrypted base64 in fleet registry ⏳
Resolves PRD open-question 1. Real mode stores SSH private keys base64 + encrypted
at rest in `ssh_keys`, decrypted only in memory. Dev mode (LocalDocker) uses no SSH
keys at all.
**Why:** keeps the fleet registry the single source of fleet truth; revisit if a
secrets manager (e.g. Vault) is introduced.

### D10 — Per-slot storage quota: 3 GB, not enforced in MVP ⏳
Resolves PRD open-question 2. Default 3 GB per slot's data; enforcement
(quota/monitoring) is post-MVP.
**Why:** quota plumbing isn't on the critical path to a working rent flow; record
the number now so it isn't re-debated.

### D11 — ToS legal placeholders ✅ (resolved 2026-05-17)
Filled by the user: Effective Date **May 1, 2026**, governing law **State of
Michigan, USA**, contact **info@akela-host.com** — applied to
`docs/terms-of-service.md` and the PRD §8 copy.
**Why:** needed before real payments. Still flagged in the doc as requiring a
Michigan-licensed attorney's review before production reliance (not code-blocking).

### D12 — Secrets never persisted; on-host root-only `.env` is the mechanism ✅
hermes needs process env, so the provisioner writes a `chmod 600` `.env` on the
agent host and references it via `env_file`. It is never written to any DB/Supabase,
never logged, scrubbed from error reports. Only `agent_api_key_hash` (bcrypt) +
non-secret config persist.
**Why:** honours the PRD's intent ("secrets never in DB/Supabase") while satisfying
the container's actual config mechanism. The PRD's literal "no `.env` file" is about
DB persistence, not the host runtime.

### D13 — Stripe webhooks idempotent via `processed_events` ✅
Every webhook event id is recorded; handlers no-op on replay. Provisioning failures
roll back the slot assignment.
**Why:** Stripe redelivers; double-provisioning would strand slots / double-bill.

### D14 — Commit policy: no co-author trailer; push to `main` proactively ✅
Commits are authored solely under the user's git credentials — **no Co-Authored-By or
"Generated with" trailer**. Commit and push to `main` regularly (after each completed
BUILD_PLAN task or meaningful chunk), working directly on `main` (no feature branch
unless the user asks). Never commit secrets.
**Why:** explicit user directive — keep authorship clean and ensure nothing is lost on
local disk between sessions. Overrides the default harness commit conventions.

### D15 — Proration formula: calendar-day, round half-up ✅
First-period charge = round(monthly_cents × remaining_days / days_in_month), where
remaining_days counts the rent day through month end. Rent on the 1st = full month.
**Why:** matches the ToS §3 "pay only for the remaining days" wording; deterministic
and trivially testable. StripeBilling delegates to Stripe's native proration; the
formula is the mock + the displayed estimate.

### D16 — Usage = live recompute, not a ledger ✅
"What you owe this month" is computed on read (sum of each active agent's prorated
amount for the current calendar month, minus referral credit). No invoices table in
Phase 2.
**Why:** Stripe remains the billing source of truth; a local ledger would duplicate
and drift. A real invoices/credits ledger is a Phase 3 concern if needed.

### D17 — Uptime = sampled health over a 30-day trailing window ✅
A sweep samples `provisioner.status` per assigned slot into `agent_health_samples`;
uptime% = healthy_samples / total_samples over the last 30 days (—" if no samples).
**Why:** no agent-side push needed; reuses the existing provisioner status call and
the sweep mechanism. Sampling cadence is a deployment/cron concern.

### D18 — Referral reward: one month credit, single-grant, no self-referral ✅
A referred user's **first successful deploy** grants the referrer 400¢ credit (one
month). Self-referral rejected; credit granted at most once per referred user.
Credit is consumed by the usage view (Epic 13), not paid out.
**Why:** abuse-resistant and simple; ties the reward to a real conversion (deploy),
not just signup. Cash payout / multi-tier is out of scope.

### D19 — Pre-launch schema is metadata-managed (single baseline migration) ✅
Supersedes the implied "incremental 0002" plan. There is no deployed database yet,
so the schema is owned by the ORM metadata: one migration (`0001`) is
`create_all`/`drop_all` of the current models (Phase 1 + 2). Tests/fresh installs
use `create_all`; the PG round-trip test validates this migration up/down. **At
launch** `0001` is frozen as the baseline and every subsequent change ships as a
real incremental migration.
**Why:** hand-written duplicate DDL across many tables drifts from the models and
adds no value while there are zero production rows to preserve. A 2nd migration
that `add_column`s what `0001`'s `create_all` already made (current models)
collides — the additive-migration model only applies once the baseline is frozen.
Reversible: freezing the baseline at launch is a one-time, well-understood step.
