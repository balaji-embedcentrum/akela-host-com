"""Billing views for the signed-in user. "What you owe this month" is recomputed
on read (D16) — Stripe stays the source of truth for actual charges."""

from __future__ import annotations

from datetime import date

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.db.models import Agent, User
from backend.dependencies import current_user, db_session
from backend.schemas.billing import UsageOut
from backend.services.usage import compute_usage

router = APIRouter(prefix="/api/billing", tags=["billing"])


@router.get("/usage", response_model=UsageOut)
async def usage(
    user: User = Depends(current_user),
    session: AsyncSession = Depends(db_session),
) -> UsageOut:
    agents = (await session.execute(select(Agent).where(Agent.user_id == user.id))).scalars().all()
    u = compute_usage(list(agents), user.credit_cents, date.today())
    return UsageOut.model_validate(u)
