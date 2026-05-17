"""Fleet registry models (schema=`fleet` in mock). Mirrors PRD §5.4. In real mode
these are Supabase tables; the mock LocalPgFleet (Epic 5) reads/writes these via the
same SQLAlchemy engine. SSH keys are absent/empty in mock (LocalDocker, D9)."""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import (
    BigInteger,
    Boolean,
    DateTime,
    ForeignKey,
    Integer,
    String,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from backend.db import FLEET_SCHEMA
from backend.db.base import FleetBase


def _uuid() -> str:
    return str(uuid.uuid4())


class VpsSshKey(FleetBase):
    __tablename__ = "vps_ssh_keys"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    name: Mapped[str] = mapped_column(String(100))
    private_key_b64: Mapped[str | None] = mapped_column(String, nullable=True)  # encrypted
    passphrase: Mapped[str | None] = mapped_column(String, nullable=True)  # encrypted
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class VpsServer(FleetBase):
    __tablename__ = "vps_servers"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    name: Mapped[str] = mapped_column(String(100))
    ip_address: Mapped[str] = mapped_column(String(45))
    ssh_user: Mapped[str] = mapped_column(String(100), default="root")
    ssh_port: Mapped[int] = mapped_column(Integer, default=22)
    ssh_key_id: Mapped[str | None] = mapped_column(
        ForeignKey(f"{FLEET_SCHEMA}.vps_ssh_keys.id"), nullable=True
    )
    location: Mapped[str | None] = mapped_column(String(100), nullable=True)
    slots_total: Mapped[int] = mapped_column(Integer, default=250)
    slots_free: Mapped[int] = mapped_column(Integer, default=250)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class AgentSlot(FleetBase):
    __tablename__ = "agent_slots"

    slot_name: Mapped[str] = mapped_column(String(100), primary_key=True)
    vps_id: Mapped[str] = mapped_column(ForeignKey(f"{FLEET_SCHEMA}.vps_servers.id"), index=True)
    slot_index: Mapped[int] = mapped_column(Integer, default=0)
    status: Mapped[str] = mapped_column(String(20), default="available", index=True)
    # available | assigned | recycling | error
    assigned_user_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    assigned_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    a2a_url: Mapped[str] = mapped_column(String(255))
    ws_url: Mapped[str] = mapped_column(String(255))
    api_key_hash: Mapped[str | None] = mapped_column(String(255), nullable=True)
    container_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    ram_limit_bytes: Mapped[int] = mapped_column(BigInteger, default=1073741824)
    vps_ip: Mapped[str] = mapped_column(String(45))  # cached from vps_servers.ip_address
