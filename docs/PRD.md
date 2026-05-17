# Akela-host.com — Product Requirements Document (PRD)

**Version:** 1.0 (MVP)
**Date:** 2026-05-17
**Status:** Under Review
**Pricing:** $4/month per Hermes Agent (prorated, per-agent)

---

## 1. Overview

### What is Akela-host.com?

Akela-host.com is a **multi-tenant SaaS hosting platform** that lets users rent **persistent Hermes AI agents** on a monthly subscription. Users select how many agents they want, pay per-agent per-month (prorated), and receive the infrastructure endpoints to connect those agents into **their own Akela AI installation** (akela-ai.com).

### The Split: Akela-host vs. Akela AI

| Concern | Akela-host.com | Akela-ai.com |
|---------|---------------|--------------|
| **Purpose** | Rent & host Hermes agents | Control plane to use agents |
| **What you get** | Running agent + A2A URL + Workspace URL | UI to chat, assign tasks, Kanban |
| **Who manages infra** | Akela-host (us) | User (self-hosted) |
| **Billing** | Monthly per-agent | Free & open source |

Users rent here → plug credentials into their own Akela AI → manage day-to-day from Akela AI.

### Multi-VPS Architecture

The web app (akela-host.com) runs on **its own VPS**. Agent containers run on **one or more separate agent-hosting VPSes**. The two are never on the same machine.

- **Supabase** holds the fleet registry: VPS IPs, pre-spawned agent URLs, slot status
- **akela-host.com** reads/writes Supabase to find available slots and route traffic
- VPSes can be swapped or rebalanced at any time by updating Supabase
- Traefik on the web app VPS proxies `agents.akela-host.com/{slug}/*` to the VPS IP stored in Supabase

---

## 2. Core Concepts

### 2.1 Agent Slots

Each agent-hosting VPS runs **250 pre-spawned Docker containers** (hermes-agent + hermes-adapter). Each container = one **slot**. Slots are permanent infrastructure — they are never destroyed, only reassigned.

Slots are tracked via a **Supabase Edge Function** that queries the fleet registry. The registry is NOT a public table — it's an internal edge function endpoint that the web app calls to find available slots and route traffic. This keeps the slot data private and prevents users from inspecting the fleet.

**Edge function interface:**
- `GET /slot/available?count=1` → returns one available slot record (vps_ip, a2a_url, workspace_url, slot_id)
- `POST /slot/assign` {slot_id, user_id, config_yaml} → assigns slot to user
- `POST /slot/unassign` {slot_id} → unassigns and returns to available pool

Slots have three states:
- **Available** — empty config, no user data, ready to rent
- **Assigned** — user's config embedded, data volume active, billing applies
- **Recycling** — config cleared, data wiped, returning to available pool

### 2.2 User Config — .env Upload (No .env stored in DB)

When a user rents an agent, they upload their own `.env` file containing their LLM API key(s) and any other secrets/tokens. This file is SSH'd directly into the agent VPS and embedded in the Docker container's environment at deploy time. The `.env` is never stored in the database or in Supabase — only the config snapshot (non-secret fields like agent name) is persisted in the `agent_slots` table.

User uploads `.env` → backend SSHs to VPS → writes to `/opt/akela-host/slots/{slot_id}/.env` → `docker compose up -d`

**Allowed .env vars (v1):**
- `ANTHROPIC_API_KEY`
- `OPENAI_API_KEY`
- `GEMINI_API_KEY`
- `HF_TOKEN`
- `GITHUB_TOKEN`
- Custom key-value pairs the user wants injected

### 2.3 VPS Configurations (Stored in Supabase Tables)

The agent-hosting VPS fleet is managed via two Supabase tables that are editable by akela-host admins at any time:

**`vps_servers`**
- `id` UUID PK
- `display_name` string — e.g. "VPS-US-East-01"
- `ip_address` string — IPv4, used for SSH + Traefik proxying
- `ssh_port` integer — default 22
- `ssh_key_id` FK → `ssh_keys` (which SSH key to use)
- `max_slots` integer — typically 250
- `is_active` boolean — toggle to take VPS offline for maintenance
- `created_at`, `updated_at` timestamps

**`vps_ssh_keys`** — stored encrypted
- `id` UUID PK
- `name` string — label for the admin (e.g. "Akela Fleet Key")
- `private_key_b64` string — base64-encoded SSH private key, stored encrypted at rest
- `passphrase` string — encrypted passphrase for the key
- `created_at` timestamp

**`agent_slots`**
- `id` UUID PK
- `vps_id` FK → `vps_servers`
- `slot_index` integer — 0-249 on that VPS
- `status` enum — `available | assigned | recycling`
- `a2a_url` string — pre-spawned URL for this slot, immutable after slot creation
- `workspace_url` string — pre-spawned URL, immutable after slot creation
- `user_id` UUID FK → users (null when available)
- `assigned_at` timestamp (null when available)
- `agent_api_key_hash` string — bcrypt hash of the agent's API key

**Routing:** Traefik on the web app VPS reads `vps_servers.ip_address` per request and proxies to the correct hosting VPS.

### 2.4 Billing Model

- Flat $4/month per agent (confirmed)
- Prorated: mid-month signup = pay only remaining days in the month
- Each rented agent = one Stripe subscription
- On cancel: agent stays active through end of billing month, then recycled

---

## 3. User Journey

### Anonymous Visitor
1. Lands on akela-host.com
2. Sees "Rent Hermes Agents — $4/month"
3. Clicks "Get Started" → GitHub OAuth login

### New User — Rent First Agent
1. Lands on dashboard: "You have no agents"
2. Clicks "Rent an Agent" → sees $4/mo pricing
3. Clicks "Subscribe" → Stripe Checkout
4. On success: backend queries Supabase for first available slot, SSH into that VPS, injects user config into docker-compose.yml, recreates container
5. User lands on "My Agents" → sees new agent card with:
   - Agent name (editable)
   - A2A endpoint URL: `https://agents.akela-host.com/{slug}/a2a`
   - Workspace URL: `https://agents.akela-host.com/{slug}/ws`
   - Agent API key (shown ONCE)
   - Monthly cost: $4
   - Renewal date
6. User copies A2A URL + Workspace URL + API key → pastes into Akela AI → agent appears online

### Returning User
1. Dashboard shows all active agents
2. Click agent → detail page with live status, renewal date, connection info
3. Actions: Update Config / Redeploy, Stop, Start, Cancel Rental

### Cancellation / Expiry
- User cancels → agent stays active through month end → recycling triggered
- Payment fails → 2-day grace → recycling triggered
- Recycling: container config cleared, data wiped, slot returns to `available`

---

## 4. Core Features

### 4.1 Landing Page (public, no auth required)
- Hero: "Rent Hermes AI agents for $4/month — persistent, fully-owned, connect to Akela AI"
- How it works (3 steps: rent → configure → connect to Akela AI)
- Fleet status widget: "247/250 agents available"
- FAQ section
- Footer: Terms, Privacy, Contact

### 4.2 Authentication

- **Supabase Auth** — GitHub OAuth + Google OAuth, via Supabase (no separate auth implementation)
- On first login: Supabase creates `auth.users` entry → our backend creates matching `public.users` record (github_id OR google_id, email, username)
- JWT session stored in HttpOnly cookie (Supabase session tokens)
- Roles: `user`, `admin`
- Edge Function `POST /auth/callback` handles post-oauth profile creation and routing

### 4.3 User Dashboard ("My Agents")
- List of user's rented agents with status badges
- "Rent Another Agent" button
- Total monthly cost shown at top
- "Fleet availability" banner

### 4.4 Rent Agent Flow
- User clicks "Rent" → Stripe Checkout (monthly $4)
- On success webhook: backend finds first `available` slot in Supabase
- Backend SSHs into that VPS → rewrites docker-compose.yml with user's config
- Backend sets `agent_slots.status = 'assigned'` + stores api_key_hash in Supabase
- Backend creates agent record in akela-host.com DB
- User sees agent card with credentials (api_key shown once)

### 4.5 Agent Detail Page
- Agent name (inline editable)
- Status: deployed / stopped / error
- Connection info (copy buttons):
  - `AKELA_API_URL` → `https://agents.akela-host.com/{slug}/a2a`
  - `AKELA_WORKSPACE_URL` → `https://agents.akela-host.com/{slug}/ws`
  - `AKELA_API_KEY` → shown ONCE after deploy, then masked
- Renewal date + monthly cost
- Actions:
  - **Update Config / Redeploy** — rewrite docker-compose.yml, wipe data, restart
  - **Stop** — `docker compose stop`, billing continues
  - **Start** — resume from stopped
  - **Cancel Rental** — confirm via modal → billing runs to month end → recycling

### 4.6 Admin Panel
- System overview: total slots, available, assigned, erroring
- Per-VPS health: which VPSes are up/down
- Per-agent status table: slot name, owner, status, RAM usage, VPS
- Actions: stop / restart / wipe data / force recycle for any agent
- All users list with agent counts

### 4.7 Stripe Billing
- Product: "Hermes Agent", $4/month, quantity = 1 per rented agent
- Checkout Session created on rent → `checkout.session.completed` webhook provisions
- Auto-renewal via Stripe subscription
- `customer.subscription.deleted` → trigger recycling
- `invoice.payment_failed` → mark agent `error`, email user

### 4.8 Email Notifications
- Welcome email on first rental
- Agent deployed confirmation (with credentials copy guide)
- 3-day renewal reminder
- Cancellation confirmed
- Agent recycled (returned to pool)
- Agent went offline (downtime alert)

---

## 5. Technical Architecture

### 5.1 Stack

| Layer | Technology |
|-------|-----------|
| Web app (akela-host.com) | FastAPI + React SPA + PostgreSQL + Traefik (own VPS) |
| Agent hosting VPSes | Docker Engine + hermes-agent + hermes-adapter containers |
| Fleet registry | Supabase (Edge Functions + tables) — VPS IPs, agent URLs, slot status |
| Remote provisioning | SSH via paramiko from web app VPS → agent VPSes |
| Auth | Supabase Auth (GitHub + Google OAuth) |
| Billing | Stripe Subscriptions |
| Email | Resend or SMTP |

### 5.2 Multi-VPS Architecture

```
                    ┌──────────────────────┐
                    │   akela-host.com     │
                    │     (web app VPS)    │
                    │  FastAPI + React     │
                    │  + PostgreSQL        │
                    └──────────┬───────────┘
                               │ SSH (paramiko)
                               │ reads/writes fleet registry
                               ▼
         ┌─────────────────────────────────────────────┐
         │              Supabase (Fleet Registry)       │
         │                                              │
         │  vps_servers: id, ip_address, ssh_key_b64,   │
         │               name, location, slots_free      │
         │                                              │
         │  agent_slots: slot_name, vps_id, status,     │
         │                a2a_url, ws_url, api_key_hash │
         │                vps_ip (cached)               │
         └─────────────────────────────────────────────┘
                    ▲          ▲          ▲
           SSH      │          │          │
          to VPS1   │      SSH to VPS2   ...
          (250 ag)  │     (250 ag)
                   │          │
         ┌─────────┴┐   ┌────┴─────────┐
         │ VPS 1     │   │ VPS 2         │
         │ hermes-   │   │ hermes-       │
         │ adapter   │   │ adapter       │
         │ containers│   │ containers    │
         └───────────┘   └───────────────┘
```

**How routing works:**
Traefik on web app VPS receives `agents.akela-host.com/{slug}/*` → reads `agent_slots.vps_ip` from Supabase → proxies to that VPS at the mapped port.

**How provisioning works:**
1. User rents → Supabase query for first `status='available'` slot
2. Backend SSHs to that VPS → rewrites docker-compose.yml with user config
3. `docker compose up -d` recreates container
4. Supabase updated: slot `assigned`, user's api_key_hash stored
5. A2A URL + Workspace URL returned to user

**How VPS swap works:**
You update `vps_servers.ip_address` and `agent_slots.vps_ip` in Supabase → Traefik picks up new target on next request. No restart needed on web app.

### 5.3 Directory Structure

```
akela-host-com/
├── docs/
│   ├── PRD.md
│   └── terms-of-service.md
├── src/
│   ├── backend/                 # FastAPI
│   │   ├── main.py
│   │   ├── config.py
│   │   ├── db/
│   │   │   ├── models.py        # SQLAlchemy: User, Agent, Subscription
│   │   │   └── session.py
│   │   ├── routers/
│   │   │   ├── auth.py          # Supabase OAuth callback + session management
│   │   │   ├── agents.py        # CRUD, deploy, recycle
│   │   │   ├── admin.py         # Fleet management
│   │   │   └── webhooks.py      # Stripe webhooks
│   │   ├── services/
│   │   │   ├── provisioning.py  # SSH + docker lifecycle
│   │   │   ├── agent_pool.py    # Find available slot from Supabase
│   │   │   ├── billing.py       # Stripe integration
│   │   │   ├── supabase.py      # Supabase client
│   │   │   └── email.py
│   │   └── schemas/             # Pydantic schemas
│   └── supabase/               # Edge Functions + migrations
│       ├── functions/
│       │   ├── slot-registry/
│       │   └── auth-callback/
│       └── migrations/
├── frontend/               # React + TS SPA
│   ├── pages/
│   │   ├── Landing.tsx
│   │   ├── Dashboard.tsx
│   │   ├── RentAgent.tsx
│   │   ├── AgentDetail.tsx
│   │   └── Admin.tsx
│   └── components/
├── infra/
│   ├── docker-compose.yml       # Dev: postgres, redis, traefik
│   └── traefik/
│       └── traefik.yml
├── scripts/
│   ├── deploy-agent.sh          # Rewrite compose + restart container
│   ├── recycle-agent.sh          # Clear config + wipe data + restart
│   └── wipe-data.sh             # Delete data volume
└── .env.example
```

### 5.4 Database Schema

**Two databases:**
- **Supabase:** Fleet registry (VPSes, agent slots, routing)
- **akela-host.com PostgreSQL:** Users, rented agents, subscriptions

```sql
-- ── SUPABASE: Fleet Registry ────────────────────────────────────────────

CREATE TABLE vps_servers (
  id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  name            VARCHAR(100) NOT NULL,     -- e.g. 'vps-us-east-1'
  ip_address      VARCHAR(45) NOT NULL,      -- IPv4 or IPv6
  ssh_user        VARCHAR(100) DEFAULT 'root',
  ssh_port        INTEGER DEFAULT 22,
  ssh_key_b64     TEXT,                      -- base64-encoded private key
  location        VARCHAR(100),             -- 'us-east', 'eu-central', etc.
  slots_total     INTEGER DEFAULT 250,
  slots_free      INTEGER DEFAULT 250,
  is_active       BOOLEAN DEFAULT TRUE,
  created_at      TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE agent_slots (
  slot_name       VARCHAR(100) PRIMARY KEY, -- 'hermesagent1'...'hermesagentN'
  vps_id          UUID REFERENCES vps_servers(id),
  status          VARCHAR(50) DEFAULT 'available', -- available|assigned|recycling|error
  assigned_user_id UUID REFERENCES auth.users(id),
  assigned_at     TIMESTAMPTZ,
  a2a_url         VARCHAR(255),             -- pre-spawned: https://{vps_ip}/{slot_name}/a2a
  ws_url          VARCHAR(255),             -- pre-spawned workspace URL
  api_key_hash    VARCHAR(255),             -- bcrypt hash of the slot's API key
  container_id    VARCHAR(255),             -- Docker container ID on that VPS
  ram_limit_bytes BIGINT DEFAULT 1073741824, -- 1GB
  vps_ip          VARCHAR(45),              -- cached: vps.ip_address
  INDEX idx_status (status),
  INDEX idx_vps_id (vps_id)
);

-- ── AKELA-HOST.COM: Web App DB ──────────────────────────────────────────

CREATE TABLE users (
  id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  github_id       VARCHAR(255) UNIQUE NOT NULL,
  github_login    VARCHAR(255) NOT NULL,
  email           VARCHAR(255),
  is_admin        BOOLEAN DEFAULT FALSE,
  created_at      TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE agents (
  id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id         UUID REFERENCES users(id),
  slot_name       VARCHAR(100) NOT NULL,    -- links to Supabase agent_slots.slot_name
  display_name    VARCHAR(255),
  status          VARCHAR(50) DEFAULT 'pending', -- pending|deployed|stopped|error
  api_key_plain   VARCHAR(255),              -- shown ONCE after deploy, then NULL
  a2a_url         VARCHAR(255),
  workspace_url   VARCHAR(255),
  monthly_cost_cents INTEGER DEFAULT 400,   -- $4.00
  billing_period_start DATE,
  billing_period_end   DATE,
  created_at      TIMESTAMPTZ DEFAULT NOW(),
  renewal_date    DATE,
  INDEX idx_user_id (user_id)
);

CREATE TABLE subscriptions (
  id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  agent_id        UUID REFERENCES agents(id),
  stripe_sub_id   VARCHAR(255) UNIQUE,
  stripe_cus_id   VARCHAR(255),
  status          VARCHAR(50),              -- active|canceled|past_due
  current_period_start DATE,
  current_period_end   DATE,
  created_at      TIMESTAMPTZ DEFAULT NOW()
);
```

### 5.5 Per-Slot Container Layout (on agent-hosting VPS)

```
/opt/akela-host/agents/{slot_name}/
├── docker-compose.yml   # Config embedded directly — NO .env file
└── data/                # Persistent workspace (git repos, files)
```

Ports (standard):
- A2A gateway: `9000` (hermes-adapter)
- Workspace API: `8766` (hermes-agent workspace)

Both ports mapped via Traefik to `agents.akela-host.com/{slot_name}/a2a` and `/ws`.

### 5.6 Security

- Agent API keys: stored bcrypt-hashed in Supabase; shown in plain ONCE after deploy then never again
- Config (API keys): embedded in docker-compose.yml — root-only readable on VPS
- No `.env` files ever created on disk
- SSH keys stored base64-encoded in Supabase, never logged or exposed
- User workspace: isolated Docker network per slot
- Traefik: TLS on all public routes

---

## 6. Out of Scope for v1

- Hermes Studio integration (not needed — users go to Akela AI)
- Akela AI running on akela-host.com
- Multiple price tiers (single $4/mo flat price)
- Any payment method other than Stripe monthly subscription
- Mobile app
- Usage analytics / token tracking per agent
- Team/workspace sharing (multiple users per org)

---

## 7. Open Questions

1. **SSH key storage** — Supabase `ssh_key_b64` (base64-encoded private key, encrypted at rest), or SSH agent, or VPS metadata service? Supabase `ssh_keys` table is the default plan.
2. **Storage limit** — Any quota per slot's `data/` directory? (Current default: 3GB per agent)
3. **Terms of Service / Privacy Policy** — See §8 below. Needed before taking payments.

---

## 8. Terms of Service Template (Unilateral — Owner-Favorable)

*Place this content at `/akela-host-com/docs/terms-of-service.md` and link from the footer. Consult a lawyer before using in production.*

---

# Terms of Service

**Effective Date:** [DATE]  
**Akela Host ("we", "us", "our")**

By accessing or using akela-host.com ("the Service"), you ("you", "your", "User") agree to be bound by these Terms of Service. If you do not agree to these terms, do not use the Service.

### 1. Service Description

Akela Host provides rental of persistent Hermes AI agent instances ("Agents") hosted on our infrastructure. Each rented Agent is a Docker container running on a VPS operated by Akela Host. The Service is provided on a month-to-month basis.

### 2. Eligibility

You must have a GitHub account to use the Service. You are responsible for ensuring your use of the Service complies with GitHub's Terms of Service.

### 3. Monthly Rental & Billing

- Rental of one (1) Hermes Agent costs **$4.00 per calendar month** (USD).
- Billing is **prorated**: if you rent an Agent mid-month, you pay only for the remaining days in that calendar month.
- Each Agent rented corresponds to one (1) monthly Stripe subscription.
- Renewals occur on the same day of each month as the initial rental date.
- You authorize us to charge your payment method on file for each monthly renewal.
- All fees are non-refundable except as required by applicable law.

### 4. Cancellation

- You may cancel a rental at any time by contacting us or using the self-service cancellation feature in your dashboard.
- Upon cancellation, your Agent remains active and accessible until the **end of the current billing period**.
- On the billing period end date: your Agent is stopped, all data in your Agent's workspace is permanently deleted within **thirty (30) days**, and the slot is returned to the available pool.
- Akela Host reserves the right to suspend or terminate any Agent at any time if we believe the Agent is being used in violation of these Terms or applicable law.

### 5. Data & Workspace

- Your Agent's workspace includes all files, git repositories, memory, and configuration associated with your rented Agent.
- **You are solely responsible for the content stored in your Agent's workspace.** You represent that you have all rights required to use any content placed in your Agent's workspace.
- Akela Host does not back up your Agent's workspace. We recommend you maintain your own backups of any critical data.
- Upon cancellation or termination, all data associated with your Agent is permanently deleted within thirty (30) days and is not recoverable.
- Akela Host may access your Agent's workspace for technical support purposes only, at your request.

### 6. User-Provided Credentials

- You are responsible for providing your own API keys, tokens, and credentials for third-party services (e.g., LLM provider API keys such as Anthropic, OpenAI, Google Gemini) that you configure in your Agent.
- Akela Host does not provide LLM API access as part of the rental fee. You must purchase LLM API access directly from the provider.
- You are solely responsible for the security of your API keys and credentials. Do not share them with unauthorized parties.
- Akela Host is not responsible for any charges incurred through your API keys or credentials.

### 7. Acceptable Use

You agree not to use the Service to:
- Violate any applicable local, state, national, or international law or regulation.
- Infringe on the intellectual property rights of any third party.
- Distribute malware, ransomware, or any malicious code.
- Engage in activities that interfere with or disrupt the Service or its underlying infrastructure.
- Use the Service to send spam, phishing, or other unsolicited communications.
- Attempt to gain unauthorized access to any other user's Agent or data.
- Use the Service in a manner that imposes an unreasonable burden on our infrastructure.

### 8. Service Level

- We target **99% monthly uptime** for the Service. Scheduled maintenance will be communicated in advance when possible.
- We do not guarantee uninterrupted access to any specific Agent.
- We reserve the right to migrate your Agent to a different underlying VPS (i.e., a different IP address) at our discretion. We will update the relevant DNS records and Supabase fleet registry accordingly.
- We are not liable for any downtime, data loss, or consequential damages arising from the use of the Service, except in cases of gross negligence or willful misconduct by Akela Host.

### 9. Agent Behavior & Liability

- You are responsible for the actions of your Agent, including any tasks it performs, content it generates, or communications it initiates.
- Akela Host is not responsible for any output, decisions, or actions taken by your Agent.
- You agree to indemnify and hold harmless Akela Host, its operators, and its affiliates from any claims, damages, or expenses arising from your use of the Service, including the actions of your Agent.

### 10. Intellectual Property

- Akela Host and its infrastructure, including but not limited to the akela-host.com website, dashboard, and provisioning system, are owned by Akela Host.
- You retain all ownership of the content stored in your Agent's workspace.
- We claim no ownership over any content created or stored by your Agent.

### 11. Third-Party Services

- Your use of third-party services (including but not limited to GitHub, Anthropic, OpenAI, Google Gemini, Supabase) is subject to those services' own terms and policies. Akela Host is not affiliated with and does not endorse or guarantee the services of any third party.

### 12. Modifications to the Service & Terms

- We may modify the Service (including pricing, features, or infrastructure) at any time with thirty (30) days' notice for material changes.
- We may modify these Terms at any time by posting the updated version on akela-host.com with an updated effective date.
- Your continued use of the Service after any modification constitutes your acceptance of the updated Terms.

### 13. Termination

- We may terminate or suspend your access to the Service immediately, without prior notice, for any reason, including breach of these Terms.
- Upon termination, all data associated with your rented Agent(s) is permanently deleted within thirty (30) days.

### 14. Limitation of Liability

- TO THE MAXIMUM EXTENT PERMITTED BY APPLICABLE LAW, AKELA HOST AND ITS AFFILIATES ARE NOT LIABLE FOR ANY INDIRECT, INCIDENTAL, SPECIAL, CONSEQUENTIAL, OR PUNITIVE DAMAGES, INCLUDING BUT NOT LIMITED TO LOSS OF PROFITS, DATA, OR GOODWILL, ARISING FROM YOUR USE OF THE SERVICE.
- IN NO EVENT SHALL AKELA HOST'S TOTAL LIABILITY EXCEED THE AMOUNT YOU PAID US IN THE TWELVE (12) MONTHS PRECEDING THE CLAIM.

### 15. Governing Law

- These Terms are governed by the laws of [YOUR JURISDICTION]. Any disputes shall be resolved in the courts of [YOUR JURISDICTION].

### 16. Contact

For questions about these Terms, contact: [YOUR EMAIL]

---

*This is a template. Replace bracketed fields `[DATE]`, `[YOUR JURISDICTION]`, `[YOUR EMAIL]` before use. This template is not legal advice.*
