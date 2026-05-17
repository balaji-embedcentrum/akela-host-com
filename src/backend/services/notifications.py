"""Lifecycle → email mapping (docs/ARCHITECTURE.md §3.5). Thin: builds the
template context and delegates to the EmailProvider. Send failures never break
the lifecycle (best-effort)."""

from __future__ import annotations

import contextlib

from backend.db.models import Agent
from backend.providers.base import EmailProvider


async def _safe(email: EmailProvider, *, to: str, template: str, context: dict) -> None:
    with contextlib.suppress(Exception):
        await email.send(to=to, template=template, context=context)


async def send_welcome(email: EmailProvider, *, to: str, username: str) -> None:
    await _safe(email, to=to, template="welcome", context={"username": username})


async def send_agent_deployed(email: EmailProvider, *, to: str, agent: Agent) -> None:
    await _safe(
        email,
        to=to,
        template="agent_deployed",
        context={
            "display_name": agent.display_name,
            "a2a_url": agent.a2a_url or "",
            "workspace_url": agent.workspace_url or "",
        },
    )


async def send_cancellation(email: EmailProvider, *, to: str, agent: Agent) -> None:
    await _safe(
        email,
        to=to,
        template="cancellation_confirmed",
        context={"display_name": agent.display_name},
    )


async def send_recycled(email: EmailProvider, *, to: str, agent: Agent) -> None:
    await _safe(
        email, to=to, template="agent_recycled", context={"display_name": agent.display_name}
    )


async def send_offline(email: EmailProvider, *, to: str, agent: Agent) -> None:
    await _safe(
        email, to=to, template="agent_offline", context={"display_name": agent.display_name}
    )


async def send_renewal_reminder(email: EmailProvider, *, to: str, agent: Agent) -> None:
    await _safe(
        email,
        to=to,
        template="renewal_reminder",
        context={
            "display_name": agent.display_name,
            "renewal_date": str(agent.renewal_date or ""),
        },
    )
