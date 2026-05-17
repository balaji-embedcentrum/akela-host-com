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

### D11 — ToS legal placeholders deferred to user ⏳
`[DATE]`, `[YOUR JURISDICTION]`, `[YOUR EMAIL]` in `docs/terms-of-service.md` are
not code-blocking and require the user/legal. Tracked in PROGRESS "Needs user".
**Why:** must be correct before taking real payments, but mock billing needs none
of it.

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
