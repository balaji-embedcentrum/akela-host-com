from __future__ import annotations

from datetime import date

from pydantic import BaseModel, ConfigDict, Field


class CheckoutIn(BaseModel):
    display_name: str = Field(min_length=1, max_length=255)


class CheckoutOut(BaseModel):
    agent_id: str
    checkout_url: str


class AgentOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    display_name: str
    status: str
    slot_name: str | None
    a2a_url: str | None
    workspace_url: str | None
    monthly_cost_cents: int
    renewal_date: date | None
    created_at: object  # serialized as ISO by FastAPI


class AgentCredentials(BaseModel):
    """Returned exactly once, right after deploy (api_key shown then nulled)."""

    agent_id: str
    a2a_url: str | None
    workspace_url: str | None
    api_key: str | None
