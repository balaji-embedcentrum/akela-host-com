from __future__ import annotations

from datetime import date

from pydantic import BaseModel, ConfigDict, Field


class CheckoutIn(BaseModel):
    display_name: str = Field(min_length=1, max_length=255)


class CheckoutOut(BaseModel):
    agent_id: str
    checkout_url: str
    first_period_cents: int  # prorated charge for the current month (D15)


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
    # Present ONLY on the detail response, the first time after deploy. Never in
    # list responses; nulled in the DB once shown (PRD §4.5).
    api_key: str | None = None


class RenameIn(BaseModel):
    display_name: str = Field(min_length=1, max_length=255)


class RedeployIn(BaseModel):
    # The user's secret env (LLM keys etc.). Passed straight to the provisioner,
    # NEVER persisted (D12). Optional — agent can run unconfigured.
    env: dict[str, str] = Field(default_factory=dict)
