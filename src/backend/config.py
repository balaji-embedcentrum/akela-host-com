"""Typed settings — single source of config truth (reads .env).

`*_MODE` switches select the mock vs real provider impl at startup. Defaults run the
full stack locally with zero external accounts (see .env.example / docs/ARCHITECTURE.md §6).
"""

from __future__ import annotations

from enum import StrEnum
from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Mode(StrEnum):
    mock = "mock"
    real = "real"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore", case_sensitive=False)

    # App
    app_env: str = "dev"
    app_base_url: str = "http://localhost:8000"
    frontend_base_url: str = "http://localhost:5173"
    agents_domain: str = "agents.akela-host.com"
    jwt_secret: str = "dev-only-change-me-min-32-bytes-please"
    session_cookie_secure: bool = False

    # Web-app database
    database_url: str = "postgresql+asyncpg://akela:akela@localhost:5432/akela_host"

    # Provider modes
    fleet_mode: Mode = Mode.mock
    billing_mode: Mode = Mode.mock
    provisioner_mode: Mode = Mode.mock
    auth_mode: Mode = Mode.mock
    email_mode: Mode = Mode.mock

    # Fleet registry
    supabase_url: str = ""
    supabase_service_role_key: str = ""
    fleet_schema: str = "fleet"
    fleet_seed_slots: int = 10

    # Billing
    stripe_secret_key: str = ""
    stripe_webhook_secret: str = ""
    stripe_price_id: str = ""
    agent_monthly_price_cents: int = 400

    # Auth
    supabase_anon_key: str = ""
    oauth_github_client_id: str = ""
    oauth_github_client_secret: str = ""
    oauth_google_client_id: str = ""
    oauth_google_client_secret: str = ""
    mock_oauth_email: str = "dev@akela-host.test"

    # Provisioner
    hermes_adapter_image: str = "hermes-adapter:latest"
    slots_host_root: str = "/opt/akela-host/slots"
    ssh_host: str = ""
    ssh_port: int = 22
    ssh_user: str = "root"

    # Email
    resend_api_key: str = ""
    email_from: str = "no-reply@akela-host.com"
    email_sink_path: str = ".dev/email-sink.jsonl"

    # Agent runtime defaults (non-secret; injected into each slot container)
    agent_workspace_dir: str = "/workspaces"
    agent_hermes_home: str = "/opt/data"
    agent_a2a_port: int = 9000
    agent_workspace_port: int = 8766


@lru_cache
def get_settings() -> Settings:
    return Settings()
