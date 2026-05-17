"""Shared email templates — used by every EmailProvider impl so subjects/bodies
stay consistent (docs/ARCHITECTURE.md §3.5). Plain-text bodies; keep them short."""

from __future__ import annotations

SUBJECTS: dict[str, str] = {
    "welcome": "Welcome to Akela Host",
    "agent_deployed": "Your Hermes agent is live",
    "renewal_reminder": "Your agent renews in 3 days",
    "cancellation_confirmed": "Your rental is cancelled",
    "agent_recycled": "Your agent has been recycled",
    "agent_offline": "Your agent went offline",
}

_BODIES: dict[str, str] = {
    "welcome": "Hi {username}, welcome to Akela Host. Rent persistent Hermes agents for $4/mo.",
    "agent_deployed": (
        "Your agent '{display_name}' is live.\n"
        "A2A URL: {a2a_url}\nWorkspace URL: {workspace_url}\n"
        "Your API key was shown once in the dashboard — store it safely."
    ),
    "renewal_reminder": "'{display_name}' renews in 3 days ({renewal_date}) for $4.",
    "cancellation_confirmed": (
        "Your rental of '{display_name}' is cancelled. It runs until the period "
        "ends, then the slot is recycled and data wiped within 30 days."
    ),
    "agent_recycled": "'{display_name}' has been recycled and its data wiped.",
    "agent_offline": "Heads up: '{display_name}' is offline (payment failed or error).",
}


class UnknownTemplate(ValueError):
    """Template name not in the known set."""


def render(template: str, context: dict) -> tuple[str, str]:
    """Return (subject, body). Missing context keys render as blanks, never crash."""
    if template not in SUBJECTS:
        raise UnknownTemplate(template)

    class _Safe(dict):
        def __missing__(self, k: str) -> str:
            return ""

    body = _BODIES[template].format_map(_Safe(context))
    return SUBJECTS[template], body
