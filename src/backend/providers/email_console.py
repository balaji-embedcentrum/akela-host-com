"""ConsoleEmail — mock EmailProvider. Renders the shared templates and appends
them as JSONL to the sink file (tests assert on it) and prints to stdout."""

from __future__ import annotations

import json
import os
from datetime import UTC, datetime

import anyio

from backend.config import Settings
from backend.providers.base import EmailProvider
from backend.providers.email_templates import render


class ConsoleEmail(EmailProvider):
    def __init__(self, settings: Settings) -> None:
        self._sink = settings.email_sink_path
        self._from = settings.email_from

    async def send(self, *, to: str, template: str, context: dict) -> None:
        subject, body = render(template, context)  # raises UnknownTemplate
        record = {
            "ts": datetime.now(UTC).isoformat(),
            "from": self._from,
            "to": to,
            "template": template,
            "subject": subject,
            "body": body,
            "context": context,
        }
        await anyio.to_thread.run_sync(self._append, record)
        print(f"[email:mock] → {to} | {subject}")

    def _append(self, record: dict) -> None:
        os.makedirs(os.path.dirname(self._sink) or ".", exist_ok=True)
        with open(self._sink, "a", encoding="utf-8") as fh:
            fh.write(json.dumps(record) + "\n")
