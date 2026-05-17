"""Uptime % over a trailing window (D17): healthy_samples / total_samples from
`agent_health_samples`. None when there are no samples yet."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from sqlalchemy import case, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.db.models import AgentHealthSample


async def uptime_pct(
    session: AsyncSession, agent_ids: list[str], *, days: int = 30
) -> dict[str, float | None]:
    """Batch: {agent_id: pct|None} for the trailing `days` window."""
    if not agent_ids:
        return {}
    cutoff = datetime.now(UTC) - timedelta(days=days)
    rows = (
        await session.execute(
            select(
                AgentHealthSample.agent_id,
                func.count().label("total"),
                func.sum(case((AgentHealthSample.healthy.is_(True), 1), else_=0)).label("ok"),
            )
            .where(
                AgentHealthSample.agent_id.in_(agent_ids),
                AgentHealthSample.ts >= cutoff,
            )
            .group_by(AgentHealthSample.agent_id)
        )
    ).all()
    seen = {
        agent_id: (round(ok / total * 100, 2) if total else None) for agent_id, total, ok in rows
    }
    return {aid: seen.get(aid) for aid in agent_ids}
