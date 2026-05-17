"""Web-app DB models — users, agents, subscriptions, processed_events.
Schema mirrors PRD §5.4 / docs/ARCHITECTURE.md §6 (auth generalized to
provider+ext_id per DECISIONS implied by Supabase GitHub+Google)."""

from __future__ import annotations

import uuid
from datetime import date, datetime

from sqlalchemy import (
    Boolean,
    Date,
    DateTime,
    ForeignKey,
    Integer,
    String,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.db.base import Base


def _uuid() -> str:
    return str(uuid.uuid4())


class User(Base):
    __tablename__ = "users"
    __table_args__ = (UniqueConstraint("provider", "ext_id", name="uq_users_provider_ext_id"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    provider: Mapped[str] = mapped_column(String(20))  # github | google | mock
    ext_id: Mapped[str] = mapped_column(String(255))
    email: Mapped[str] = mapped_column(String(255))
    username: Mapped[str] = mapped_column(String(255))
    is_admin: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    agents: Mapped[list[Agent]] = relationship(back_populates="user", lazy="selectin")


class Agent(Base):
    __tablename__ = "agents"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True)
    # Logical link to fleet.agent_slots.slot_name — intentionally NOT an FK.
    slot_name: Mapped[str | None] = mapped_column(String(100), nullable=True)
    display_name: Mapped[str] = mapped_column(String(255))
    status: Mapped[str] = mapped_column(String(20), default="pending")
    # pending | deployed | stopped | error | recycled
    api_key_plain: Mapped[str | None] = mapped_column(String(255), nullable=True)
    a2a_url: Mapped[str | None] = mapped_column(String(255), nullable=True)
    workspace_url: Mapped[str | None] = mapped_column(String(255), nullable=True)
    monthly_cost_cents: Mapped[int] = mapped_column(Integer, default=400)
    billing_period_start: Mapped[date | None] = mapped_column(Date, nullable=True)
    billing_period_end: Mapped[date | None] = mapped_column(Date, nullable=True)
    renewal_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    user: Mapped[User] = relationship(back_populates="agents", lazy="selectin")
    subscription: Mapped[Subscription | None] = relationship(
        back_populates="agent", uselist=False, lazy="selectin"
    )


class Subscription(Base):
    __tablename__ = "subscriptions"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    agent_id: Mapped[str] = mapped_column(ForeignKey("agents.id"), index=True)
    stripe_sub_id: Mapped[str | None] = mapped_column(String(255), unique=True, nullable=True)
    stripe_cus_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    status: Mapped[str] = mapped_column(String(20), default="active")  # active|canceled|past_due
    current_period_start: Mapped[date | None] = mapped_column(Date, nullable=True)
    current_period_end: Mapped[date | None] = mapped_column(Date, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    agent: Mapped[Agent] = relationship(back_populates="subscription")


class ProcessedEvent(Base):
    """Billing webhook idempotency (docs/ARCHITECTURE.md §5.4 / D13)."""

    __tablename__ = "processed_events"

    event_id: Mapped[str] = mapped_column(String(255), primary_key=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
