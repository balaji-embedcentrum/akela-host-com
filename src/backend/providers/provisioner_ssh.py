"""SshProvisioner — real AgentProvisioner. SSHes to the slot's VPS, writes the
per-slot compose + a root-only `.env` (API_SERVER_KEY + user secrets, chmod 600,
NEVER in any DB — D12), and drives `docker compose`. `paramiko` is lazy-imported
so mock mode never needs it. Credential-gated; exercised only with a real VPS."""

from __future__ import annotations

import shlex

import anyio

from backend.config import Settings
from backend.providers.base import (
    AgentProvisioner,
    DeployResult,
    ProviderError,
    Slot,
    SlotRuntimeStatus,
)
from backend.providers.compose import build_env, container_name, render_compose


class SshProvisioner(AgentProvisioner):
    def __init__(self, settings: Settings) -> None:
        if not settings.ssh_host and not settings.slots_host_root:
            raise ProviderError("SshProvisioner requires SSH/host configuration")
        self._settings = settings
        self._root = settings.slots_host_root

    def _connect(self, vps_ip: str):
        import paramiko

        client = paramiko.SSHClient()
        client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        client.connect(
            vps_ip,
            port=self._settings.ssh_port,
            username=self._settings.ssh_user,
            timeout=15,
        )
        return client

    def _ssh(self, vps_ip: str, commands: list[str], files: dict[str, str]) -> None:
        client = self._connect(vps_ip)
        try:
            sftp = client.open_sftp()
            for path, content in files.items():
                with sftp.file(path, "w") as fh:
                    fh.write(content)
                if path.endswith(".env"):
                    sftp.chmod(path, 0o600)  # secrets readable only by root
            sftp.close()
            for cmd in commands:
                _, stdout, stderr = client.exec_command(cmd)
                if stdout.channel.recv_exit_status() != 0:
                    raise ProviderError(f"remote cmd failed: {cmd}: {stderr.read().decode()}")
        finally:
            client.close()

    def _slot_dir(self, slot: Slot) -> str:
        return f"{self._root}/{slot.slot_name}"

    async def deploy(
        self, slot: Slot, *, user_env: dict[str, str], agent_api_key: str, display_name: str
    ) -> DeployResult:
        d = self._slot_dir(slot)
        env = build_env(
            slot,
            settings=self._settings,
            agent_api_key=agent_api_key,
            display_name=display_name,
            user_env=user_env,
        )
        env_file = "\n".join(f"{k}={v}" for k, v in env.items())
        compose = render_compose(
            slot, settings=self._settings, display_name=display_name, host_dir=d
        )
        try:
            await anyio.to_thread.run_sync(
                self._ssh,
                slot.vps_ip,
                [
                    f"mkdir -p {shlex.quote(d)}/data {shlex.quote(d)}/workspaces",
                    f"cd {shlex.quote(d)} && docker compose up -d",
                ],
                {f"{d}/docker-compose.yml": compose, f"{d}/.env": env_file},
            )
        except Exception as exc:
            raise ProviderError(f"ssh deploy failed for {slot.slot_name}: {exc}") from exc
        return DeployResult(
            container_id=container_name(slot.slot_name), a2a_url=slot.a2a_url, ws_url=slot.ws_url
        )

    async def stop(self, slot: Slot) -> None:
        await anyio.to_thread.run_sync(
            self._ssh,
            slot.vps_ip,
            [f"cd {shlex.quote(self._slot_dir(slot))} && docker compose stop"],
            {},
        )

    async def start(self, slot: Slot) -> None:
        await anyio.to_thread.run_sync(
            self._ssh,
            slot.vps_ip,
            [f"cd {shlex.quote(self._slot_dir(slot))} && docker compose start"],
            {},
        )

    async def recycle(self, slot: Slot) -> None:
        d = self._slot_dir(slot)
        await anyio.to_thread.run_sync(
            self._ssh,
            slot.vps_ip,
            [
                f"cd {shlex.quote(d)} && docker compose down -v || true",
                f"rm -rf {shlex.quote(d)}",  # wipe data + workspaces + .env
            ],
            {},
        )

    async def status(self, slot: Slot) -> SlotRuntimeStatus:
        try:
            await anyio.to_thread.run_sync(
                self._ssh,
                slot.vps_ip,
                [f"docker inspect -f '{{{{.State.Running}}}}' {container_name(slot.slot_name)}"],
                {},
            )
            return SlotRuntimeStatus(running=True, health="running")
        except ProviderError:
            return SlotRuntimeStatus(running=False, health="absent")
