"""LocalDockerProvisioner — mock AgentProvisioner. Same logic the SSH provisioner
runs on a VPS, but against the local Docker daemon: the host IS the "VPS"
(docs/ARCHITECTURE.md §3.3, §6). Per-slot host dirs live under ./.localfleet/
(git-ignored); the user's env is passed straight to the container and never
persisted (D12)."""

from __future__ import annotations

import shutil
from pathlib import Path

import anyio
import httpx

from backend.config import Settings
from backend.providers.base import (
    AgentProvisioner,
    DeployResult,
    ProviderError,
    Slot,
    SlotRuntimeStatus,
)
from backend.providers.compose import build_env, container_name

_LOCAL_ROOT = Path(".localfleet")


class LocalDockerProvisioner(AgentProvisioner):
    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._ws_port = settings.agent_workspace_port
        self._a2a_port = settings.agent_a2a_port
        self._image = settings.hermes_adapter_image

    # ---- docker client (lazy; SDK only here, never imported elsewhere) ----
    def _client(self):
        import docker

        return docker.from_env()

    def _host_dir(self, slot_name: str) -> Path:
        return _LOCAL_ROOT / slot_name

    # ---- blocking docker ops, run off the event loop ----
    def _remove_existing(self, name: str) -> None:
        client = self._client()
        try:
            old = client.containers.get(name)
            old.remove(force=True)
        except Exception:
            pass

    def _run(self, slot: Slot, env: dict[str, str], host_dir: Path) -> str:
        client = self._client()
        (host_dir / "data").mkdir(parents=True, exist_ok=True)
        (host_dir / "workspaces").mkdir(parents=True, exist_ok=True)
        c = client.containers.run(
            self._image,
            name=container_name(slot.slot_name),
            detach=True,
            environment=env,
            volumes={
                str((host_dir / "data").resolve()): {
                    "bind": self._settings.agent_hermes_home,
                    "mode": "rw",
                },
                str((host_dir / "workspaces").resolve()): {
                    "bind": self._settings.agent_workspace_dir,
                    "mode": "rw",
                },
            },
            ports={f"{self._ws_port}/tcp": None, f"{self._a2a_port}/tcp": None},
            labels={"akela.slot": slot.slot_name},
        )
        return c.id

    def _host_port(self, name: str, container_port: int) -> int | None:
        client = self._client()
        c = client.containers.get(name)
        c.reload()
        binding = c.attrs["NetworkSettings"]["Ports"].get(f"{container_port}/tcp")
        return int(binding[0]["HostPort"]) if binding else None

    def _container_state(self, name: str) -> tuple[bool, str]:
        client = self._client()
        try:
            c = client.containers.get(name)
        except Exception:
            return False, "absent"
        c.reload()
        running = c.status == "running"
        health = (c.attrs.get("State", {}).get("Health") or {}).get(
            "Status", "running" if running else c.status
        )
        return running, health

    def _docker_action(self, name: str, action: str) -> None:
        client = self._client()
        c = client.containers.get(name)
        getattr(c, action)()

    # ---- AgentProvisioner ----
    async def deploy(
        self, slot: Slot, *, user_env: dict[str, str], agent_api_key: str, display_name: str
    ) -> DeployResult:
        env = build_env(
            slot,
            settings=self._settings,
            agent_api_key=agent_api_key,
            display_name=display_name,
            user_env=user_env,
        )
        name = container_name(slot.slot_name)
        host_dir = self._host_dir(slot.slot_name)
        await anyio.to_thread.run_sync(self._remove_existing, name)
        try:
            container_id = await anyio.to_thread.run_sync(self._run, slot, env, host_dir)
        except Exception as exc:  # image missing, daemon error, …
            raise ProviderError(f"deploy failed for {slot.slot_name}: {exc}") from exc

        port = await anyio.to_thread.run_sync(self._host_port, name, self._ws_port)
        if port is None:
            raise ProviderError("no host port bound for the workspace API")
        await self._await_health(port)
        return DeployResult(container_id=container_id, a2a_url=slot.a2a_url, ws_url=slot.ws_url)

    async def _await_health(self, host_port: int, wait_seconds: float = 40.0) -> None:
        url = f"http://127.0.0.1:{host_port}/health"
        deadline = anyio.current_time() + wait_seconds
        async with httpx.AsyncClient(timeout=3) as c:
            while anyio.current_time() < deadline:
                try:
                    r = await c.get(url)
                    if r.status_code < 500:
                        return
                except httpx.HTTPError:
                    pass
                await anyio.sleep(0.5)
        raise ProviderError(f"agent health check timed out ({url})")

    async def stop(self, slot: Slot) -> None:
        await anyio.to_thread.run_sync(self._docker_action, container_name(slot.slot_name), "stop")

    async def start(self, slot: Slot) -> None:
        await anyio.to_thread.run_sync(self._docker_action, container_name(slot.slot_name), "start")

    async def recycle(self, slot: Slot) -> None:
        await anyio.to_thread.run_sync(self._remove_existing, container_name(slot.slot_name))
        # Wipe data + workspaces — nothing of the previous tenant survives (ToS §4).
        await anyio.to_thread.run_sync(
            lambda: shutil.rmtree(self._host_dir(slot.slot_name), ignore_errors=True)
        )

    async def status(self, slot: Slot) -> SlotRuntimeStatus:
        running, health = await anyio.to_thread.run_sync(
            self._container_state, container_name(slot.slot_name)
        )
        return SlotRuntimeStatus(running=running, health=health)
