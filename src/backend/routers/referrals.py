"""Referral program (D18). Share `?ref=<code>`; a referred user's first deploy
grants you one month of credit, applied automatically in the usage view."""

from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.db.models import User
from backend.dependencies import current_user, db_session
from backend.schemas.referrals import ReferralOut

router = APIRouter(prefix="/api/referrals", tags=["referrals"])


@router.get("/me", response_model=ReferralOut)
async def my_referral(
    user: User = Depends(current_user),
    session: AsyncSession = Depends(db_session),
) -> ReferralOut:
    referred_count = (
        await session.execute(
            select(func.count()).select_from(User).where(User.referred_by_user_id == user.id)
        )
    ).scalar_one()
    return ReferralOut(
        code=user.referral_code,
        referred_count=referred_count,
        earned_cents=user.credit_cents,
    )
