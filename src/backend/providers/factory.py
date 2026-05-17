"""The ONLY place that branches on `*_MODE`. Maps (kind, mode) → impl class and
builds it lazily so the app can boot while later epics' impls don't exist yet
(see docs/ARCHITECTURE.md §3, CLAUDE.md)."""

from __future__ import annotations

import importlib
from dataclasses import dataclass
from typing import Literal

from backend.config import Settings
from backend.providers.base import (
    AgentProvisioner,
    AuthProvider,
    BillingProvider,
    EmailProvider,
    FleetRegistry,
    ProviderNotImplemented,
)

Kind = Literal["fleet", "billing", "provisioner", "auth", "email"]

# (kind, mode) → "module:Class". Impls land in their respective epics.
_REGISTRY: dict[tuple[str, str], str] = {
    ("fleet", "mock"): "backend.providers.fleet_local:LocalPgFleet",
    ("fleet", "real"): "backend.providers.fleet_supabase:SupabaseFleet",
    ("billing", "mock"): "backend.providers.billing_fake:FakeBilling",
    ("billing", "real"): "backend.providers.billing_stripe:StripeBilling",
    ("provisioner", "mock"): "backend.providers.provisioner_local:LocalDockerProvisioner",
    ("provisioner", "real"): "backend.providers.provisioner_ssh:SshProvisioner",
    ("auth", "mock"): "backend.providers.auth_mock:MockOAuth",
    ("auth", "real"): "backend.providers.auth_supabase:SupabaseAuth",
    ("email", "mock"): "backend.providers.email_console:ConsoleEmail",
    ("email", "real"): "backend.providers.email_resend:ResendEmail",
}


def build_provider(kind: Kind, settings: Settings):
    """Construct one provider. Impl ctor takes `settings` and owns its own resources."""
    mode = getattr(settings, f"{kind}_mode")
    spec = _REGISTRY.get((kind, str(mode)))
    if spec is None:  # pragma: no cover - guarded by typing
        raise ProviderNotImplemented(f"no impl registered for {kind}/{mode}")
    module_path, class_name = spec.split(":")
    try:
        module = importlib.import_module(module_path)
    except ModuleNotFoundError as exc:
        raise ProviderNotImplemented(
            f"{kind}/{mode} not built yet ({module_path}). See docs/BUILD_PLAN.md."
        ) from exc
    return getattr(module, class_name)(settings)


@dataclass(slots=True)
class Providers:
    fleet: FleetRegistry
    billing: BillingProvider
    provisioner: AgentProvisioner
    auth: AuthProvider
    email: EmailProvider


def build_providers(settings: Settings) -> Providers:
    """Resolve all five from `*_MODE`. Raises ProviderNotImplemented if any selected
    impl module is absent (caught by main.lifespan during incremental dev)."""
    return Providers(
        fleet=build_provider("fleet", settings),
        billing=build_provider("billing", settings),
        provisioner=build_provider("provisioner", settings),
        auth=build_provider("auth", settings),
        email=build_provider("email", settings),
    )
