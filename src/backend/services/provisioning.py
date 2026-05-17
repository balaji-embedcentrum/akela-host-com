"""Rent->deploy orchestration (docs/ARCHITECTURE.md section 5). Called from the
billing webhook once an agent is `paid`: claim a slot, deploy the container,
record connection info. Any failure rolls the slot back so none is stranded."""

from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from backend.db.models import Agent
from backend.providers.base import AgentProvisioner, FleetRegistry, ProviderError
from backend.security import generate_api_key, hash_api_key
from backend.services.agent_pool import claim_slot


async def provision_paid_agent(
    agent: Agent,
    *,
    session: AsyncSession,
    fleet: FleetRegistry,
    provisioner: AgentProvisioner,
    user_env: dict[str, str] | None = None,
) -> str:
    """Idempotent at the caller (billing handler only calls this on the first
    `paid` outcome). Returns the resulting agent status."""
    if agent.slot_name:  # already provisioned — never double-deploy
        return agent.status

    api_key = generate_api_key()  # the AKELA_API_KEY — shown once, only hash stored
    key_hash = hash_api_key(api_key)
    slot = await claim_slot(fleet, user_id=agent.user_id, api_key_hash=key_hash)

    try:
        result = await provisioner.deploy(
            slot,
            user_env=user_env or {},
            agent_api_key=api_key,
            display_name=agent.display_name,
        )
    except ProviderError:
        await fleet.unassign_slot(slot.slot_name)  # don't strand the slot
        agent.status = "error"
        return agent.status

    agent.slot_name = slot.slot_name
    agent.a2a_url = result.a2a_url
    agent.workspace_url = result.ws_url
    agent.api_key_plain = api_key  # surfaced once via GET /agents/{id}, then nulled
    agent.status = "deployed"
    return agent.status


async def recycle_agent(
    agent: Agent,
    *,
    fleet: FleetRegistry,
    provisioner: AgentProvisioner,
) -> None:
    """Stop + wipe the container and return the slot to the pool (ToS §4)."""
    if not agent.slot_name:
        agent.status = "recycled"
        return
    slot = await fleet.get_slot(agent.slot_name)
    if slot is not None:
        try:
            await provisioner.recycle(slot)
        except ProviderError:
            pass  # best-effort wipe; slot still returns to the pool
        await fleet.unassign_slot(slot.slot_name)
    agent.status = "recycled"
    agent.api_key_plain = None
