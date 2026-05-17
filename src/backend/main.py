"""FastAPI app factory.

Providers are resolved once at startup from `*_MODE` settings (see providers/factory.py)
and exposed via `app.state` for dependency injection. No router/service imports an
external SDK directly — only the provider impls do (architecture rule, tested in
tests/test_architecture.py).
"""

from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend import __version__
from backend.config import get_settings


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()
    # Lazy import so Epic 0 (no providers yet) still boots; wired from Epic 1 on.
    try:
        from backend.providers.factory import build_providers

        app.state.providers = build_providers(settings)
    except ModuleNotFoundError:
        app.state.providers = None
    yield


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(title="akela-host.com", version=__version__, lifespan=lifespan)

    app.add_middleware(
        CORSMiddleware,
        allow_origins=[settings.frontend_base_url],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.get("/health", tags=["meta"])
    async def health() -> dict[str, str]:
        return {"status": "ok", "version": __version__, "env": settings.app_env}

    # Routers are mounted as epics land; importing lazily keeps Epic 0 bootable.
    for module, attr in (
        ("backend.routers.auth", "router"),
        ("backend.routers.agents", "router"),
        ("backend.routers.admin", "router"),
        ("backend.routers.webhooks", "router"),
        ("backend.routers.fleet_mock", "router"),
        ("backend.routers.routing", "router"),
    ):
        try:
            mod = __import__(module, fromlist=[attr])
            app.include_router(getattr(mod, attr))
        except ModuleNotFoundError:
            continue

    return app


app = create_app()
