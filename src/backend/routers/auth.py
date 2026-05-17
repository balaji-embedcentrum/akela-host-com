"""Auth routes — OAuth login/callback (Supabase or mock), JWT session cookie,
user upsert, roles. Offline-complete in mock mode (docs/ARCHITECTURE.md §5.5)."""

from __future__ import annotations

import jwt
from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response, status
from fastapi.responses import RedirectResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.config import Settings
from backend.db.models import User
from backend.dependencies import current_user, db_session, get_auth, get_settings_dep
from backend.providers.base import AuthProvider
from backend.ratelimit import RateLimit
from backend.schemas.auth import UserOut
from backend.security import SESSION_COOKIE, issue_session, issue_state, read_state

router = APIRouter(prefix="/api/auth", tags=["auth"])

_ALLOWED_PROVIDERS = {"github", "google", "mock"}


def _safe_redirect(path: str) -> str:
    # Only same-site absolute paths — never an open redirect.
    return path if path.startswith("/") and not path.startswith("//") else "/dashboard"


@router.get("/login", dependencies=[Depends(RateLimit("login", 50))])
async def login(
    request: Request,
    provider: str = Query("mock"),
    redirect: str = Query("/dashboard"),
    settings: Settings = Depends(get_settings_dep),
    auth: AuthProvider = Depends(get_auth),
) -> RedirectResponse:
    if provider not in _ALLOWED_PROVIDERS:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "unsupported provider")
    state = issue_state(settings.jwt_secret, redirect=_safe_redirect(redirect), provider=provider)
    redirect_uri = f"{settings.app_base_url}/api/auth/callback"
    url = auth.authorize_url(provider=provider, state=state, redirect_uri=redirect_uri)
    return RedirectResponse(url, status_code=status.HTTP_302_FOUND)


@router.get("/callback")
async def callback(
    code: str,
    state: str,
    settings: Settings = Depends(get_settings_dep),
    auth: AuthProvider = Depends(get_auth),
    session: AsyncSession = Depends(db_session),
) -> RedirectResponse:
    try:
        st = read_state(settings.jwt_secret, state)
    except jwt.PyJWTError as exc:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "invalid state") from exc

    redirect_uri = f"{settings.app_base_url}/api/auth/callback"
    try:
        identity = await auth.exchange(code=code, redirect_uri=redirect_uri)
    except ValueError as exc:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "auth exchange failed") from exc

    user = (
        await session.execute(
            select(User).where(User.provider == identity.provider, User.ext_id == identity.ext_id)
        )
    ).scalar_one_or_none()
    if user is None:
        user = User(
            provider=identity.provider,
            ext_id=identity.ext_id,
            email=identity.email,
            username=identity.username,
        )
        session.add(user)
        await session.flush()
    else:  # keep profile fresh; never downgrade is_admin here
        user.email = identity.email
        user.username = identity.username

    token = issue_session(
        settings.jwt_secret, user_id=user.id, email=user.email, is_admin=user.is_admin
    )
    target = settings.frontend_base_url + _safe_redirect(st["redirect"])
    resp = RedirectResponse(target, status_code=status.HTTP_302_FOUND)
    resp.set_cookie(
        SESSION_COOKIE,
        token,
        httponly=True,
        secure=settings.session_cookie_secure,
        samesite="lax",
        max_age=7 * 24 * 3600,
    )
    return resp


@router.post("/logout")
async def logout(response: Response) -> dict[str, bool]:
    response.delete_cookie(SESSION_COOKIE)
    return {"ok": True}


@router.get("/me", response_model=UserOut)
async def me(user: User = Depends(current_user)) -> User:
    return user
