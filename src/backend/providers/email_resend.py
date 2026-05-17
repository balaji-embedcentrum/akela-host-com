"""ResendEmail — real EmailProvider via Resend. Credential-gated; `resend` is
lazy-imported so mock mode never needs it (architecture rule)."""

from __future__ import annotations

import anyio

from backend.config import Settings
from backend.providers.base import EmailProvider, ProviderError
from backend.providers.email_templates import render


class ResendEmail(EmailProvider):
    def __init__(self, settings: Settings) -> None:
        if not settings.resend_api_key:
            raise ProviderError("ResendEmail requires RESEND_API_KEY")
        self._key = settings.resend_api_key
        self._from = settings.email_from

    async def send(self, *, to: str, template: str, context: dict) -> None:
        subject, body = render(template, context)

        def _send() -> None:
            import resend  # lazy: real-mode only

            resend.api_key = self._key
            resend.Emails.send({"from": self._from, "to": [to], "subject": subject, "text": body})

        await anyio.to_thread.run_sync(_send)
