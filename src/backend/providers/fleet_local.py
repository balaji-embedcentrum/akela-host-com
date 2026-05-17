"""LocalPgFleet — mock FleetRegistry over the `fleet` schema (same engine as the
web DB locally; SQLite collapses the schema for tests). The slot claim is a single
atomic UPDATE … WHERE status='available' so concurrent rents can't double-assign
(docs/ARCHITECTURE.md §3.1, §7)."""

from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import select, update

from backend.config import Settings
from backend.db.fleet_models import AgentSlot
from backend.db.session import get_database_for
from backend.providers.base import (
    FleetRegistry,
    RouteTarget,
    Slot,
    SlotStatus,
    SlotUnavailable,
)


class LocalPgFleet(FleetRegistry):
    def __init__(self, settings: Settings) -> None:
        self._db = get_database_for(settings.database_url)
        self._a2a_port = settings.agent_a2a_port
        self._ws_port = settings.agent_workspace_port

    def _to_slot(self, row: AgentSlot) -> Slot:
        return Slot(
            slot_name=row.slot_name,
            vps_id=row.vps_id,
            vps_ip=row.vps_ip,
            status=SlotStatus(row.status),
            a2a_url=row.a2a_url,
            ws_url=row.ws_url,
            a2a_port=self._a2a_port,
            ws_port=self._ws_port,
            assigned_user_id=row.assigned_user_id,
        )

    async def get_available_slot(self) -> Slot | None:
        async with self._db.sessionmaker() as s:
            row = (
                await s.execute(
                    select(AgentSlot)
                    .where(AgentSlot.status == SlotStatus.available)
                    .order_by(AgentSlot.slot_index)
                    .limit(1)
                )
            ).scalar_one_or_none()
            return self._to_slot(row) if row else None

    async def assign_slot(self, slot_name: str, user_id: str, api_key_hash: str) -> Slot:
        async with self._db.sessionmaker() as s:
            row = (
                await s.execute(
                    update(AgentSlot)
                    .where(
                        AgentSlot.slot_name == slot_name,
                        AgentSlot.status == SlotStatus.available,
                    )
                    .values(
                        status=SlotStatus.assigned,
                        assigned_user_id=user_id,
                        api_key_hash=api_key_hash,
                        assigned_at=datetime.now(UTC),
                    )
                    .returning(AgentSlot)
                )
            ).scalar_one_or_none()
            if row is None:
                await s.rollback()
                raise SlotUnavailable(f"slot {slot_name} was not available")
            await s.commit()
            return self._to_slot(row)

    async def unassign_slot(self, slot_name: str) -> None:
        async with self._db.sessionmaker() as s:
            await s.execute(
                update(AgentSlot)
                .where(AgentSlot.slot_name == slot_name)
                .values(
                    status=SlotStatus.available,
                    assigned_user_id=None,
                    api_key_hash=None,
                    assigned_at=None,
                    container_id=None,
                )
            )
            await s.commit()

    async def get_slot(self, slot_name: str) -> Slot | None:
        async with self._db.sessionmaker() as s:
            row = await s.get(AgentSlot, slot_name)
            return self._to_slot(row) if row else None

    async def resolve_route(self, slot_name: str) -> RouteTarget | None:
        slot = await self.get_slot(slot_name)
        if slot is None:
            return None
        return RouteTarget(
            slot_name=slot.slot_name,
            vps_ip=slot.vps_ip,
            a2a_port=slot.a2a_port,
            ws_port=slot.ws_port,
        )

    async def list_slots(self, status: SlotStatus | None = None) -> list[Slot]:
        async with self._db.sessionmaker() as s:
            stmt = select(AgentSlot).order_by(AgentSlot.slot_index)
            if status is not None:
                stmt = stmt.where(AgentSlot.status == status)
            rows = (await s.execute(stmt)).scalars().all()
            return [self._to_slot(r) for r in rows]
