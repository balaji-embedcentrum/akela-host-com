"""Provider interfaces (ABCs) + shared DTOs. Keep signatures stable — mode differences
live behind these. See docs/ARCHITECTURE.md §3."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import StrEnum

# ───────────────────────── DTOs ─────────────────────────


class SlotStatus(StrEnum):
    available = "available"
    assigned = "assigned"
    recycling = "recycling"
    error = "error"


@dataclass(slots=True)
class Slot:
    slot_name: str
    vps_id: str
    vps_ip: str
    status: SlotStatus
    a2a_url: str
    ws_url: str
    a2a_port: int = 9000
    ws_port: int = 8766
    assigned_user_id: str | None = None


@dataclass(slots=True)
class RouteTarget:
    slot_name: str
    vps_ip: str
    a2a_port: int
    ws_port: int


@dataclass(slots=True)
class CheckoutSession:
    id: str
    url: str
    customer_ref: str | None = None
    subscription_ref: str | None = None


class BillingEventType(StrEnum):
    checkout_completed = "checkout.session.completed"
    subscription_deleted = "customer.subscription.deleted"
    payment_failed = "invoice.payment_failed"
    unknown = "unknown"


@dataclass(slots=True)
class BillingEvent:
    type: BillingEventType
    event_id: str
    customer_id: str | None = None
    subscription_id: str | None = None
    client_reference_id: str | None = None  # our pending agent id
    raw: dict = field(default_factory=dict)


@dataclass(slots=True)
class DeployResult:
    container_id: str
    a2a_url: str
    ws_url: str


@dataclass(slots=True)
class SlotRuntimeStatus:
    running: bool
    health: str  # "healthy" | "starting" | "unhealthy" | "absent"
    detail: str = ""


@dataclass(slots=True)
class ExternalIdentity:
    provider: str  # "github" | "google" | "mock"
    ext_id: str
    email: str
    username: str


# ───────────────────────── Interfaces ─────────────────────────


class FleetRegistry(ABC):
    """Slot allocation + routing. Real=Supabase, mock=local Postgres `fleet` schema."""

    @abstractmethod
    async def get_available_slot(self) -> Slot | None: ...

    @abstractmethod
    async def assign_slot(self, slot_name: str, user_id: str, api_key_hash: str) -> Slot:
        """Atomic claim (WHERE status='available'). Raises SlotUnavailable on race."""

    @abstractmethod
    async def unassign_slot(self, slot_name: str) -> None: ...

    @abstractmethod
    async def get_slot(self, slot_name: str) -> Slot | None: ...

    @abstractmethod
    async def resolve_route(self, slot_name: str) -> RouteTarget | None: ...

    @abstractmethod
    async def list_slots(self, status: SlotStatus | None = None) -> list[Slot]: ...


class BillingProvider(ABC):
    """Subscription lifecycle. Real=Stripe, mock=in-process fake."""

    @abstractmethod
    async def create_checkout(
        self, *, client_reference_id: str, email: str, success_url: str, cancel_url: str
    ) -> CheckoutSession: ...

    @abstractmethod
    def parse_webhook(self, *, headers: dict, body: bytes) -> BillingEvent:
        """Verify signature + return typed event. Raises on bad signature."""

    @abstractmethod
    async def cancel_subscription(self, subscription_id: str) -> None: ...


class AgentProvisioner(ABC):
    """Per-slot hermes-adapter container lifecycle. Real=SSH, mock=local Docker."""

    @abstractmethod
    async def deploy(
        self, slot: Slot, *, user_env: dict[str, str], agent_api_key: str, display_name: str
    ) -> DeployResult: ...

    @abstractmethod
    async def stop(self, slot: Slot) -> None: ...

    @abstractmethod
    async def start(self, slot: Slot) -> None: ...

    @abstractmethod
    async def recycle(self, slot: Slot) -> None:
        """Stop, wipe data + workspaces, clear injected config; slot reusable."""

    @abstractmethod
    async def status(self, slot: Slot) -> SlotRuntimeStatus: ...


class AuthProvider(ABC):
    """OAuth. Real=Supabase Auth (GitHub/Google), mock=deterministic identity."""

    @abstractmethod
    def authorize_url(self, *, state: str, redirect_uri: str) -> str: ...

    @abstractmethod
    async def exchange(self, *, code: str, redirect_uri: str) -> ExternalIdentity: ...


class EmailProvider(ABC):
    """Transactional email. Real=Resend/SMTP, mock=console/file sink."""

    @abstractmethod
    async def send(self, *, to: str, template: str, context: dict) -> None: ...


# ───────────────────────── Errors ─────────────────────────


class ProviderError(RuntimeError):
    """Base for provider-layer failures."""


class SlotUnavailable(ProviderError):
    """No available slot, or a concurrent rent won the atomic claim."""


class ProviderNotImplemented(ProviderError):
    """The selected (provider, mode) impl has not been built yet."""


class WebhookVerificationError(ProviderError):
    """Billing webhook signature failed verification."""
