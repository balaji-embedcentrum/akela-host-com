"""ConsoleEmail — mock EmailProvider. Renders templates and appends them as JSONL to
the sink file (tests assert on it) and prints to stdout. Reference impl that proves
the interface + factory + contract-test pattern (real ResendEmail lands in Epic 9)."""

from __future__ import annotations

import json
import os
from datetime import UTC, datetime

import anyio

from backend.config import Settings
from backend.providers.base import EmailProvider

# Subject lines per lifecycle template (bodies are rendered from context generically).
TEMPLATES: dict[str, str] = {
    "welcome": "Welcome to Akela Host",
    "agent_deployed": "Your Hermes agent is live",
    "renewal_reminder": "Your agent renews in 3 days",
    "cancellation_confirmed": "Your rental is cancelled",
    "agent_recycled": "Your agent has been recycled",
    "agent_offline": "Your agent went offline",
}


class UnknownTemplate(ValueError):
    """Template name not in the known set."""


class ConsoleEmail(EmailProvider):
    def __init__(self, settings: Settings) -> None:
        self._sink = settings.email_sink_path
        self._from = settings.email_from

    async def send(self, *, to: str, template: str, context: dict) -> None:
        if template not in TEMPLATES:
            raise UnknownTemplate(template)
        record = {
            "ts": datetime.now(UTC).isoformat(),
            "from": self._from,
            "to": to,
            "template": template,
            "subject": TEMPLATES[template],
            "context": context,
        }
        await anyio.to_thread.run_sync(self._append, record)
        print(f"[email:mock] → {to} | {TEMPLATES[template]} | {context}")

    def _append(self, record: dict) -> None:
        os.makedirs(os.path.dirname(self._sink) or ".", exist_ok=True)
        with open(self._sink, "a", encoding="utf-8") as fh:
            fh.write(json.dumps(record) + "\n")
