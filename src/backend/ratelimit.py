"""Tiny in-process fixed-window rate limiter (docs/ARCHITECTURE.md §7). Per-app
state (so tests are isolated); single-VPS MVP — swap for Redis when multi-VPS."""

from __future__ import annotations

import time

from fastapi import Depends, HTTPException, Request, status

from backend.config import Settings
from backend.dependencies import get_settings_dep


class RateLimit:
    """Use as a route dependency: `Depends(RateLimit("login", 50))`."""

    def __init__(self, bucket: str, per_minute: int) -> None:
        self.bucket = bucket
        self.per_minute = per_minute

    def __call__(self, request: Request, settings: Settings = Depends(get_settings_dep)) -> None:
        if settings.app_env == "test_disabled":  # escape hatch, unused by default
            return
        store: dict = request.app.state.__dict__.setdefault("_rl", {})
        now = time.time()
        window = int(now // 60)
        key = (self.bucket, request.client.host if request.client else "?", window)
        count = store.get(key, 0) + 1
        store[key] = count
        # prune old windows occasionally
        if len(store) > 4096:
            for k in [k for k in store if k[2] < window]:
                store.pop(k, None)
        if count > self.per_minute:
            raise HTTPException(
                status.HTTP_429_TOO_MANY_REQUESTS, "rate limit exceeded; retry shortly"
            )
