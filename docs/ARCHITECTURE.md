# Architecture — akela-host.com

The *how*. The PRD (`docs/PRD.md`) is the *what*; where this document and the PRD
disagree on a runtime fact, this document wins and the disagreement is recorded in
`docs/DECISIONS.md`.

---

## 1. System topology

```
                       ┌─────────────────────────────┐
                       │      akela-host.com         │
                       │       (web-app VPS)         │
   browser ───────────▶│  React SPA  ·  FastAPI      │
                       │  Postgres (users/agents/    │
                       │            subscriptions)   │
                       │  Traefik (dynamic router)   │
                       └───┬─────────────┬───────────┘
                           │             │ provider interfaces
            fleet registry │             │ (mock | real)
                           ▼             ▼
              ┌────────────────┐   ┌──────────┐   ┌──────────────┐
              │ Supabase       │   │ Stripe   │   │ Agent host(s)│
              │ vps_servers    │   │ subs +   │   │ slot pool of │
              │ agent_slots    │   │ webhooks │   │ hermes-      │
              │ ssh_keys       │   │          │   │ adapter      │
              │ edge functions │   │          │   │ containers   │
              └────────────────┘   └──────────┘   └──────────────┘

  agents.akela-host.com/{slot}/a2a  ──▶ Traefik ──▶ agent_slots.vps_ip:9000
  agents.akela-host.com/{slot}/ws   ──▶ Traefik ──▶ agent_slots.vps_ip:8766
```

In **local-first dev** everything in the bottom row is replaced by a local
implementation (see §6). The web-app code path is identical either way — only the
provider implementation swaps.

---

## 2. Component responsibilities

| Component        | Owns                                                                 |
|------------------|----------------------------------------------------------------------|
| React SPA        | Landing, auth redirect, dashboard, rent flow, agent detail, admin    |
| FastAPI          | Auth callback, agents CRUD/lifecycle, Stripe webhooks, admin, routing data |
| Web-app Postgres | `users`, `agents`, `subscriptions` (PRD §5.4)                         |
| Fleet registry   | `vps_servers`, `agent_slots`, `ssh_keys` — slot allocation + routing  |
| Provisioner      | Push user `.env` to host, render per-slot compose, (re)start container |
| Billing          | Checkout session, subscription lifecycle, webhook → provisioning      |
| Traefik          | Per-request dynamic proxy `{slot}` → the slot's host:port             |

---

## 3. Provider abstraction layer (the spine of local-first)

Every external system is reached only through an interface in
`src/backend/services/providers/`. Concrete impls are selected at startup from
`*_MODE` env vars. A single **contract test suite** runs against *both* impls so the
mock can never silently drift from the real one.

```
providers/
├── fleet.py        FleetRegistry      (.find_available_slot, .assign, .unassign,
│                                       .get_route, .list_vps, .slot_status)
├── billing.py      BillingProvider    (.create_checkout, .cancel, .parse_webhook)
├── provisioner.py  AgentProvisioner   (.deploy(slot, env, config),
│                                       .stop, .start, .recycle, .stats)
├── auth.py         AuthProvider       (.authorize_url, .exchange, .verify_session)
└── email.py        EmailProvider      (.send(template, to, ctx))
```

Real impls: `SupabaseFleet`, `StripeBilling`, `SshProvisioner`, `SupabaseAuth`,
`ResendEmail`. Mock impls: `LocalPgFleet`, `FakeBilling`, `LocalDockerProvisioner`,
`MockOAuth`, `ConsoleEmail`. **No router or service may import `stripe`, `paramiko`,
`supabase`, etc. directly** — only through these interfaces.

---

## 4. Key sequences

### 4.1 Rent → provision (the critical path)

```
User clicks Rent
  → POST /agents/checkout            (creates pending agent row, status=pending)
  → BillingProvider.create_checkout  → redirect user to (mock|real) checkout
  → [payment succeeds] webhook: checkout.session.completed
  → webhook handler (idempotent on event id):
      1. FleetRegistry.find_available_slot()         → slot or 409 (pool exhausted)
      2. FleetRegistry.assign(slot, user_id)         → slot=assigned (optimistic lock)
      3. generate agent API key; bcrypt → store hash in fleet + agents row
      4. AgentProvisioner.deploy(slot, user_env, {API_SERVER_KEY=key, AGENT_NAME, …})
      5. agents.status = deployed; persist a2a_url, workspace_url, api_key_plain (once)
      6. EmailProvider.send("agent_deployed", …)
  → user polls GET /agents/{id}; sees credentials exactly once
```

Failure handling: every step after (2) that fails triggers `FleetRegistry.unassign`
+ `agents.status=error` so a failed deploy never strands a slot. Webhook handler is
idempotent — replaying the same Stripe event id is a no-op.

### 4.2 Cancel → recycle

```
Cancel (user) or customer.subscription.deleted or invoice.payment_failed(+grace)
  → mark subscription canceled; agent stays "deployed" until period_end
  → at period_end (scheduled sweep):
      AgentProvisioner.recycle(slot)  → stop container, wipe /workspaces + /opt/data,
                                        clear injected env
      FleetRegistry.unassign(slot)    → status=available, user_id=null
      agents.status = recycled
      EmailProvider.send("agent_recycled", …)
```

Workspace data retention: PRD/ToS promise deletion **within 30 days** of
cancellation — recycle may defer the wipe up to that window; MVP wipes immediately
and records the choice in DECISIONS.

### 4.3 Traefik dynamic routing

Traefik does not get a static config per slot. A small FastAPI endpoint serves
Traefik's HTTP provider (or a file provider regenerated on slot change):
`agents.akela-host.com/{slot}/(a2a|ws)` → look up `agent_slots.vps_ip` →
proxy to `vps_ip:9000` / `vps_ip:8766`. A VPS swap is just an UPDATE to
`agent_slots.vps_ip`; routing picks it up on the next provider refresh — no web-app
restart. In local-first the "vps_ip" is the local Docker network address of the
slot container.

### 4.4 OAuth callback

`AuthProvider.authorize_url` → provider → `GET /auth/callback` →
`AuthProvider.exchange(code)` returns `{provider_id, email, login}` →
upsert `users` (by `github_id`/google id) → issue session JWT in HttpOnly cookie.
`MockOAuth` skips the redirect and returns a deterministic identity so the whole
flow is testable offline.

---

## 5. Hermes per-slot contract

Deployable unit = **the `hermes-adapter` image only** (agent embedded via
`FROM nousresearch/hermes-agent:latest`). Per-slot compose the provisioner renders:

```yaml
services:
  agent:
    image: hermes-adapter:latest
    container_name: slot-${SLOT_NAME}
    environment:
      HERMES_ADAPTER_HOST: 0.0.0.0
      HERMES_ADAPTER_PORT: 8766          # workspace API
      A2A_HOST: 0.0.0.0
      A2A_PORT: 9000                     # A2A gateway (NOT 9001)
      API_SERVER_KEY: ${AGENT_API_KEY}   # == PRD AKELA_API_KEY (preferred over A2A_KEY)
      A2A_PUBLIC_URL: https://agents.akela-host.com/${SLOT_NAME}/a2a
      AGENT_NAME: ${DISPLAY_NAME}
      HERMES_WORKSPACE_DIR: /workspaces
      HERMES_HOME: /opt/data
      # ↓ user-supplied .env injected verbatim (OPENROUTER_API_KEY, GOOGLE_API_KEY,
      #   HF_TOKEN, GITHUB_TOKEN, custom k/v). We do NOT validate or rename keys.
    env_file: [ /opt/akela-host/slots/${SLOT_NAME}/.env ]
    volumes:
      - /opt/akela-host/slots/${SLOT_NAME}/workspaces:/workspaces
      - /opt/akela-host/slots/${SLOT_NAME}/data:/opt/data
    healthcheck:
      test: ["CMD", "curl", "-sf", "http://localhost:8766/health"]
      interval: 30s
      timeout: 5s
      retries: 3
```

Note the PRD says "config embedded in compose, no `.env` file on disk". The hermes
images consume an `env_file`/process env; we use a root-only `.env` written by the
provisioner and **never** stored in any DB. The PRD's "no `.env`" intent (secrets
never persisted in DB/Supabase) is honoured; the on-host root-only file is the
mechanism. Recorded in DECISIONS D7/D12.

---

## 6. Local-first dev topology

`make dev` brings up: Postgres, Traefik, and the backend/frontend. There is **no
VPS and no Supabase**:

- **Fleet registry** → `LocalPgFleet`: the Supabase tables live as an extra schema
  in the same Postgres; "edge functions" are plain FastAPI internal routes. Seeded
  with one fake VPS = `localhost`/local Docker network and N slots.
- **Provisioner** → `LocalDockerProvisioner`: talks to the local Docker daemon via
  the Docker SDK instead of SSH+remote `docker compose`. Renders the same compose
  template; slots are real local containers. `vps_ip` = container DNS name.
- **Billing** → `FakeBilling`: `create_checkout` returns a local URL that, when
  hit, emits a signed `checkout.session.completed` to our own webhook — exercising
  the real handler end to end.
- **Auth** → `MockOAuth`. **Email** → `ConsoleEmail` (writes to a file sink the
  tests assert on).

Graduating a single concern to real = flip its `*_MODE=real` and supply creds;
nothing else changes. This is why the provider boundary is strict.

---

## 7. Data model notes (beyond PRD §5.4)

- Two stores, **no cross-store FK**. `agents.slot_name` ↔
  `agent_slots.slot_name` is reconciled in application code; a nightly consistency
  check flags orphans (assigned slot with no live agent, or vice-versa).
- `agents.api_key_plain` is populated only between deploy and first successful
  fetch by the owner, then nulled. Only `*_hash` (bcrypt) persists long-term.
- Slot allocation uses an atomic conditional update
  (`UPDATE … SET status='assigned' WHERE slot_name=? AND status='available'`
  returning row) to prevent two concurrent rents grabbing the same slot.
- Stripe webhook idempotency: a `processed_events(event_id)` table; handler is a
  no-op on replay.

---

## 8. Security rules (enforced, not aspirational)

- Agent API key: bcrypt-hashed at rest; plaintext shown once, never logged.
- User `.env`: pushed to host, root-only (`chmod 600`), never in any DB/Supabase,
  never logged, scrubbed from error reports.
- SSH private keys (real mode): stored base64 + encrypted at rest in the fleet
  registry; decrypted only in memory by the provisioner; never logged.
- All public agent routes are TLS via Traefik; per-slot isolated Docker network.
- The fleet registry is never exposed to the browser — only the backend reads it.

---

## 9. Known PRD discrepancies (see DECISIONS.md for resolutions)

| PRD says | Reality | Resolution |
|----------|---------|------------|
| A2A port 9000; (adapter Dockerfile 9001) | code/compose default **9000** | use 9000 — D5 |
| Allowed env incl. `ANTHROPIC_API_KEY` | hermes routes via `OPENROUTER_API_KEY`/`GOOGLE_API_KEY` | pass user `.env` through verbatim, don't validate — D7 |
| No `.env` file anywhere | hermes needs process env; root-only host `.env`, never in DB | honour intent (no DB secrets) — D12 |
| Two containers (agent + adapter) | adapter image embeds agent — one container | one container/slot — D4 |
| Build slot model from scratch | hermes-adapter already has fleet/manifest mode | MVP wraps with our own compose; revisit reuse — D8 |
