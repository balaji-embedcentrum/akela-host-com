from __future__ import annotations

from pydantic import BaseModel


class ReferralOut(BaseModel):
    code: str
    referred_count: int
    earned_cents: int
