from __future__ import annotations

from pydantic import BaseModel, ConfigDict


class UsageLineOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    agent_id: str
    display_name: str
    days_charged: int
    amount_cents: int


class UsageOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    month: str
    items: list[UsageLineOut]
    subtotal_cents: int
    credit_cents: int
    total_cents: int
