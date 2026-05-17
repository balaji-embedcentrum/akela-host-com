"""FastAPI dependency wiring. Tests override `get_settings_dep` (→ sqlite + all
mock) and everything else follows. Providers are built per-request from settings
via the factory (the only mode-branching point)."""

from __future__ import annotations

from collections.abc import AsyncIterator
from functools import lru_cache

import jwt
from fastapi import Depends, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.config import Settings, get_settings
from backend.db.models import User
from backend.db.session import Database
from backend.providers.base import AuthProvider, BillingProvider, EmailProvider
from backend.providers.factory import build_provider
from backend.security import SESSION_COOKIE, read_session


def get_settings_dep() -> Settings:
    """Overridden in tests to inject sqlite + mock settings."""
    return get_settings()


@lru_cache(maxsize=8)
def _database_for(url: str) -> Database:
    return Database(url)


def get_database(settings: Settings = Depends(get_settings_dep)) -> Database:
    return _database_for(settings.database_url)


async def db_session(
    database: Database = Depends(get_database),
) -> AsyncIterator[AsyncSession]:
    async with database.sessionmaker() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise


def get_auth(settings: Settings = Depends(get_settings_dep)) -> AuthProvider:
    return build_provider("auth", settings)


def get_email(settings: Settings = Depends(get_settings_dep)) -> EmailProvider:
    return build_provider("email", settings)


def get_billing(settings: Settings = Depends(get_settings_dep)) -> BillingProvider:
    return build_provider("billing", settings)


async def current_user(
    request: Request,
    settings: Settings = Depends(get_settings_dep),
    session: AsyncSession = Depends(db_session),
) -> User:
    token = request.cookies.get(SESSION_COOKIE)
    if not token:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "not authenticated")
    try:
        claims = read_session(settings.jwt_secret, token)
    except jwt.PyJWTError as exc:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "invalid session") from exc
    user = (
        await session.execute(select(User).where(User.id == claims["sub"]))
    ).scalar_one_or_none()
    if user is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "user not found")
    return user


async def require_admin(user: User = Depends(current_user)) -> User:
    if not user.is_admin:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "admin only")
    return user
