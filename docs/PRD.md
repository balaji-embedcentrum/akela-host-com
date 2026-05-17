# Akela-host.com — Product Requirements Document (PRD)

**Version:** 1.0 (MVP)  
**Date:** 2026-05-17  
**Status:** Under Review — $4/mo per agent confirmed

---

## 1. Overview

### What is Akela-host.com?

Akela-host.com is a **multi-tenant SaaS hosting platform** that lets users rent **persistent Hermes AI agents** on a monthly subscription basis. Users select how many agents they want, pay per-agent per-month (prorated), and receive the infrastructure endpoints they need to connect those agents into their own Akela AI installation.

### The Split: Akela-host vs. Akela AI

| Concern | Akela-host.com | Akela-ai.com |
|---------|---------------|--------------|
| **Purpose** | Rent & host Hermes agents | Control plane to manage agents |
| **What you get** | Running agent + workspace API | UI to chat, assign tasks, Kanban |
| **Who manages infra** | Akela-host (us) | User (self-hosted) |
| **Billing** | Monthly per-agent | Free & open source |

Users rent agents here → plug them into their own Akela AI → manage day-to-day from Akela AI.

---

## 2. User Journey

### Anonymous Visitor
1. Lands on akela-host.com landing page
2. Reads value proposition ("Rent Hermes agents for $X/mo")
3. Clicks "Get Started" → GitHub OAuth login

### Signed-in User — First Time
1. Lands on dashboard — "You have no agents"
2. Clicks "Rent an Agent" → sees pricing ("1 agent = $Y/month")
3. Clicks "Subscribe" → Stripe Checkout (monthly subscription per agent)
4. On success: system provisions a Hermes Adapter + hermes-agent container
5. User lands on "My Agents" page — sees new agent card with:
   - Agent name (editable)
   - A2A endpoint URL (e.g. `https://agents.akela-host.com/{agent-slug}/a2a`)
   - Workspace API URL (e.g. `https://agents.akela-host.com/{agent-slug}/ws`)
   - Agent API key (for Akela AI bridge auth)
   - Monthly cost
   - Renewal date
6. User copies the three pieces of info (A2A URL, Workspace URL, API key) into their Akela AI → agent appears online in Akela AI

### Signed-in User — Returning
1. Dashboard shows all active agents with renewal dates
2. Click agent → detail view with:
   - Live status (online/offline based on heartbeat)
   - Resource usage (CPU, memory — Docker stats)
   - Renewal date + next billing amount
   - Actions: Stop, Restart, Delete (with confirmation)
3. "Rent Another Agent" → Stripe again → new agent provisioned

### Billing / Cancellation
- User cancels subscription in Stripe portal → on renewal date, agent is stopped and deleted (grace period: 7 days after failed payment)
- Agent deleted → workspace data retained for 30 days then purged
- Monthly email reminder 3 days before renewal

---

## 3. Core Features

### 3.1 Landing Page (Public)
- Hero section with headline, sub-headline, CTA ("Rent a Hermes Agent")
- Features section (what Hermes agents can do, why rent via Akela-host)
- Pricing section (simple: 1 agent = $X/month)
- FAQ section
- Footer with links (Terms, Privacy, Contact)

### 3.2 Authentication
- GitHub OAuth only (no email/password for v1)
- On first login: create user record in DB
- Roles: `user` (default), `admin`
- Session managed via JWT (stored in HttpOnly cookie)

### 3.3 User Dashboard ("My Agents")
- List of all agents the user has rented
- Each agent card shows: name, status (online/offline), monthly cost, renewal date
- "Rent New Agent" prominent CTA
- Total monthly cost shown at top

### 3.4 Agent Provisioning
When user successfully subscribes via Stripe:
1. Generate unique `agent_slug` (e.g. `raj-alpha-7x2k9`)
2. Create user namespace/project in database
3. Spawn Docker container for `hermes-adapter` + `hermes-agent` using a template
4. Assign agent URL, workspace URL, generate API key
5. Send welcome email with setup instructions (link to Akela AI docs)
6. Show agent detail page

### 3.5 Agent Detail Page
- Agent name (editable inline)
- Status badge (online/offline/error)
- **Connection Info section** (read-only display, copy buttons):
  - `AKELA_API_URL` → Agent A2A endpoint
  - `AKELA_WORKSPACE_URL` → Workspace API endpoint
  - `AKELA_API_KEY` → Bearer token
- Agent since (creation date)
- Renewal date
- Monthly cost
- **Actions:**
  - Restart agent (recreate container)
  - Delete agent (with "type agent name to confirm" flow)

### 3.6 Admin Panel
- View all users, all agents
- For any agent: stop/start/delete container
- View billing status (Stripe subscription states)
- System health: total agents, running count, erroring count

### 3.7 Email Notifications (v1 — simple)
- Welcome email on first agent provisioned
- Renewal reminder 3 days before
- Cancellation confirmation
- Agent deleted (after grace period)
- Agent went offline (if downtime detected)

---

## 4. Technical Architecture

### 4.1 Stack

| Layer | Technology |
|-------|-----------|
| Frontend | React 18 + TypeScript + Vite (SPA, served as static) |
| Backend API | Python 3.12 + FastAPI |
| Database | PostgreSQL 16 |
| Container runtime | Docker (per-agent containers) |
| Reverse proxy | Traefik v2 (routes agents.akela-host.com/*) |
| Auth | GitHub OAuth + JWT |
| Billing | Stripe Subscriptions (per-agent) |
| Email | Resend (or SMTP) |
| Hosting | Single VPS (or scalable to multi-VPS) |

### 4.2 Directory Structure

```
akela-host-com/
├── docs/
│   ├── PRD.md              ← this file
│   └── api-reference.md    ← future
├── src/
│   ├── frontend/           # React + TS + Vite SPA
│   │   ├── pages/          # Landing, Dashboard, AgentDetail, Admin, Auth
│   │   ├── components/     # Shared UI components
│   │   └── lib/            # API client
│   ├── backend/            # FastAPI
│   │   ├── main.py
│   │   ├── config.py
│   │   ├── db/             # SQLAlchemy models
│   │   ├── routers/        # auth, agents, admin, webhooks
│   │   ├── services/       # provisioning, docker, stripe, email
│   │   └── schemas/        # Pydantic schemas
│   └── infra/              # Docker compose + Traefik config
│       ├── docker-compose.yml
│       └── traefik/
├── .env.example
└── README.md
```

### 4.3 Database Schema

**users** — created on first GitHub OAuth login
- `id` UUID PK
- `github_id` string UNIQUE
- `github_username` string
- `email` string
- `created_at` timestamp

**agents** — one per rented agent
- `id` UUID PK
- `user_id` UUID FK → users
- `slug` string UNIQUE (e.g. `raj-alpha-7x2k9`)
- `name` string (user-editable)
- `api_key` string UNIQUE (generated)
- `a2a_url` string
- `workspace_url` string
- `status` enum (pending | running | stopped | error)
- `container_id` string (Docker container ID)
- `monthly_price_cents` integer
- `created_at` timestamp
- `renewal_date` date

**subscriptions** — Stripe subscription per agent
- `id` UUID PK
- `agent_id` UUID FK → agents
- `stripe_subscription_id` string
- `stripe_customer_id` string
- `status` string (active | canceled | past_due)
- `current_period_start` date
- `current_period_end` date

### 4.4 Docker Agent Provisioning

Each agent = a Docker Compose project on the host:

```
/opt/akela-host/agents/{agent_slug}/
├── docker-compose.yml   # hermes-agent + hermes-adapter
├── .env                 # AGENT_API_KEY, ANTHROPIC_API_KEY (user provides or we provide), etc.
└── data/                # persistent workspace (git repos, files)
```

Traefik routes `agents.akela-host.com/{agent_slug}/a2a` → port 9000  
Traefik routes `agents.akela-host.com/{agent_slug}/ws` → port 8766

### 4.5 Stripe Integration

- Product: "Hermes Agent" at $X/month (configurable)
- When user subscribes: create `Customer` → create `Subscription` (quantity = 1 per agent)
- Webhook handler: `checkout.session.completed` → provision agent
- Webhook handler: `customer.subscription.deleted` → deprovision agent
- Webhook handler: `invoice.payment_failed` → mark agent as `error` + email user

### 4.6 Security Considerations

- Agent API keys: stored hashed in DB, shown once in full after creation
- User workspace: isolated Docker network per agent
- Traefik: TLS on all public routes
- Backend: JWT auth, rate limiting, input validation
- No agent containers get inbound access to the host filesystem

---

## 5. Out of Scope for v1

- Hermes Studio integration
- Akela AI running on akela-host.com
- Multiple agent tiers / plans (1 agent = 1 price)
- Paying for agents with anything other than Stripe monthly subscription
- Mobile app
- Agent usage analytics
- Team/workspace sharing (multiple users per org)

---

## 6. Roadmap

### Phase 1 — MVP (This Build)
1. Landing page (public, no auth required to view)
2. GitHub OAuth sign-in
3. User dashboard — list agents
4. Stripe checkout — subscribe to rent 1 agent
5. Agent provisioning — Docker container spawns
6. Agent detail page — show connection info (A2A URL, workspace URL, API key)
7. Agent stop / restart / delete
8. Basic admin panel
9. Email notifications
10. Deploy to VPS, push to GitHub

### Phase 2 — Billing & Trust
1. Stripe Billing integration with proration (mid-month signup = pay only what you use)
2. Usage billing view in dashboard (what you owe this month)
3. Agent trust/reliability display (uptime %)
4. Referral program

### Phase 3 — Scale
1. Multi-VPS agent hosting (agent fleet spread across hosts)
2. Agent marketplace (pre-configured agent personas)
3. Usage analytics per agent
4. WebSocket-based live agent status dashboard

---

## 7. Open Questions

1. **Pricing** — What is the monthly price per agent? Needs to be set before Stripe product is created.
2. **Agent model** — Do we provide the AI model (Anthropic/OpenAI API key), or does the user bring their own? If we provide it, we need to factor in token costs + margin.
3. **Workspace limits** — Any storage limit per agent's workspace? (git repos, files)
4. **Concurrency** — Can one user rent multiple agents? Yes by design. Any cap?
5. **Deletion grace period** — 30 days workspace retention after cancellation — acceptable?
6. **Terms of Service / Privacy Policy** — Need legal pages before taking payments.
