"""Traefik dynamic-routing source (docs/ARCHITECTURE.md §4.3/§5.3). Built per
request from the fleet registry so a VPS swap is just a registry edit — no web-app
restart. Served to Traefik's HTTP provider as JSON."""

from __future__ import annotations

from backend.config import Settings
from backend.providers.base import Slot


def build_traefik_dynamic(slots: list[Slot], settings: Settings) -> dict:
    routers: dict[str, dict] = {}
    services: dict[str, dict] = {}
    host = settings.agents_domain

    for slot in slots:
        for kind, port in (("a2a", slot.a2a_port), ("ws", slot.ws_port)):
            name = f"{slot.slot_name}-{kind}"
            routers[name] = {
                "rule": f"Host(`{host}`) && PathPrefix(`/{slot.slot_name}/{kind}`)",
                "service": name,
                "entryPoints": ["web"],
            }
            services[name] = {
                "loadBalancer": {"servers": [{"url": f"http://{slot.vps_ip}:{port}"}]}
            }

    return {"http": {"routers": routers, "services": services}}
