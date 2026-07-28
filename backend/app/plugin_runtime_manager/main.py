from __future__ import annotations

import asyncio
import logging
import os
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import AsyncSessionFactory, close_database
from app.models.plugins import (
    GuildPluginInstallation,
    PluginRuntimeInstance,
)
from app.plugin_runtime_manager.sandbox import (
    SandboxLimits,
    apply_sandbox,
)
from app.plugin_sdk.runtime_tokens import (
    create_runtime_token,
)

logger = logging.getLogger("shieldnet.plugin_runtime.manager")


@dataclass
class ManagedProcess:
    process: asyncio.subprocess.Process
    generation: int
    package_path: str
    entrypoint: str
    restart_count: int = 0
    last_heartbeat_monotonic: float = 0.0


class PluginRuntimeManager:
    def __init__(self) -> None:
        self.poll_seconds = float(
            os.getenv("PLUGIN_RUNTIME_POLL_SECONDS", "2")
        )
        self.heartbeat_seconds = float(
            os.getenv("PLUGIN_RUNTIME_HEARTBEAT_SECONDS", "15")
        )
        self.stop_timeout_seconds = float(
            os.getenv("PLUGIN_RUNTIME_STOP_TIMEOUT_SECONDS", "10")
        )
        self.max_restarts = int(
            os.getenv("PLUGIN_RUNTIME_MAX_RESTARTS", "5")
        )

        self.processes: dict[
            tuple[int, str],
            ManagedProcess,
        ] = {}

        self.python_executable = Path(sys.executable)
        self.sandbox_limits = SandboxLimits.from_env()

    async def list_instances(
        self,
        session: AsyncSession,
    ) -> list[PluginRuntimeInstance]:
        return list(
            (
                await session.execute(
                    select(PluginRuntimeInstance)
                )
            ).scalars().all()
        )

    @staticmethod
    def resolve_entrypoint(
        instance: PluginRuntimeInstance,
    ) -> str:
        manifest = instance.manifest_json or {}
        entrypoint = manifest.get("entrypoint")

        if not isinstance(entrypoint, str) or not entrypoint:
            raise RuntimeError(
                "Plugin manifest has no valid entrypoint"
            )

        package_path = Path(instance.package_path or "").resolve()
        entrypoint_path = (package_path / entrypoint).resolve()

        if package_path not in entrypoint_path.parents:
            raise RuntimeError(
                "Plugin entrypoint escapes package directory"
            )

        if not entrypoint_path.is_file():
            raise RuntimeError(
                f"Plugin entrypoint not found: {entrypoint_path}"
            )

        return entrypoint

    async def spawn(
        self,
        instance: PluginRuntimeInstance,
        *,
        restart_count: int = 0,
    ) -> ManagedProcess:
        if not instance.package_path:
            raise RuntimeError("Runtime instance has no package_path")

        entrypoint = self.resolve_entrypoint(instance)

        manifest = instance.manifest_json or {}
        raw_permissions = manifest.get("capabilities", [])

        if not isinstance(raw_permissions, list) or any(
            not isinstance(permission, str)
            for permission in raw_permissions
        ):
            raise RuntimeError(
                "Plugin manifest permissions must be a string list"
            )

        command = [
            str(self.python_executable),
            "-m",
            "app.plugin_runtime_manager.runner",
            "--guild-id",
            str(instance.guild_id),
            "--plugin-key",
            instance.plugin_key,
            "--package-path",
            instance.package_path,
            "--entrypoint",
            entrypoint,
            "--generation",
            str(instance.generation),
        ]

        for permission in sorted(set(raw_permissions)):
            command.extend([
                "--permission",
                permission,
            ])

        logger.info(
            "Starting plugin plugin_key=%s guild_id=%s generation=%s",
            instance.plugin_key,
            instance.guild_id,
            instance.generation,
        )

        runtime_token = create_runtime_token(
            plugin_key=instance.plugin_key,
            guild_id=instance.guild_id,
            generation=instance.generation,
            permissions=frozenset(raw_permissions),
        )

        plugin_environment = {
            "SHIELDNET_RUNTIME_TOKEN": runtime_token,
            "SHIELDNET_BACKEND_URL": os.getenv(
                "PLUGIN_RUNTIME_BACKEND_URL",
                "http://127.0.0.1:8000/api/v1",
            ),
            "PATH": os.getenv(
                "PLUGIN_RUNTIME_PATH",
                "/usr/local/bin:/usr/bin:/bin",
            ),
            "LANG": os.getenv("LANG", "C.UTF-8"),
            "LC_ALL": os.getenv("LC_ALL", "C.UTF-8"),
            "PYTHONUNBUFFERED": "1",
            "PYTHONDONTWRITEBYTECODE": "1",
            "PYTHONPATH": str(
                Path(__file__).resolve().parents[2]
            ),
            "HOME": instance.package_path,
            "TMPDIR": "/tmp",
            "SHIELDNET_PLUGIN_KEY": instance.plugin_key,
            "SHIELDNET_GUILD_ID": str(instance.guild_id),
            "SHIELDNET_PLUGIN_GENERATION": str(
                instance.generation
            ),
        }

        limits = self.sandbox_limits

        process = await asyncio.create_subprocess_exec(
            *command,
            cwd=instance.package_path,
            env=plugin_environment,
            start_new_session=True,
            preexec_fn=lambda: apply_sandbox(limits),
        )

        return ManagedProcess(
            process=process,
            generation=instance.generation,
            package_path=instance.package_path,
            entrypoint=entrypoint,
            restart_count=restart_count,
            last_heartbeat_monotonic=0.0,
        )

    async def terminate(
        self,
        key: tuple[int, str],
        managed: ManagedProcess,
    ) -> None:
        process = managed.process

        if process.returncode is not None:
            self.processes.pop(key, None)
            return

        logger.info(
            "Stopping plugin plugin_key=%s guild_id=%s pid=%s",
            key[1],
            key[0],
            process.pid,
        )

        process.terminate()

        try:
            await asyncio.wait_for(
                process.wait(),
                timeout=self.stop_timeout_seconds,
            )
        except asyncio.TimeoutError:
            logger.warning(
                "Plugin did not stop gracefully; killing "
                "plugin_key=%s guild_id=%s pid=%s",
                key[1],
                key[0],
                process.pid,
            )
            process.kill()
            await process.wait()

        self.processes.pop(key, None)

    async def mark_error_and_stop(
        self,
        instance: PluginRuntimeInstance,
        error: str,
    ) -> None:
        async with AsyncSessionFactory() as session:
            row = (
                await session.execute(
                    select(PluginRuntimeInstance).where(
                        PluginRuntimeInstance.guild_id
                        == instance.guild_id,
                        PluginRuntimeInstance.plugin_key
                        == instance.plugin_key,
                    )
                )
            ).scalar_one_or_none()

            if row is None:
                return

            now = datetime.now(timezone.utc)
            row.state = "stopped"
            row.stopped_at = now
            row.updated_at = now
            row.last_error = error[:8000]

            installation = (
                await session.execute(
                    select(GuildPluginInstallation).where(
                        GuildPluginInstallation.guild_id
                        == instance.guild_id,
                        GuildPluginInstallation.plugin_key
                        == instance.plugin_key,
                    )
                )
            ).scalar_one_or_none()

            if installation is not None:
                installation.status = "error"
                installation.last_error = error[:8000]
                installation.last_health_check_at = now
                installation.updated_at = now

            await session.commit()

    async def heartbeat(
        self,
        instance: PluginRuntimeInstance,
    ) -> None:
        async with AsyncSessionFactory() as session:
            row = (
                await session.execute(
                    select(PluginRuntimeInstance).where(
                        PluginRuntimeInstance.guild_id
                        == instance.guild_id,
                        PluginRuntimeInstance.plugin_key
                        == instance.plugin_key,
                        PluginRuntimeInstance.state == "running",
                    )
                )
            ).scalar_one_or_none()

            if row is None:
                return

            installation = (
                await session.execute(
                    select(GuildPluginInstallation).where(
                        GuildPluginInstallation.guild_id
                        == instance.guild_id,
                        GuildPluginInstallation.plugin_key
                        == instance.plugin_key,
                    )
                )
            ).scalar_one_or_none()

            now = datetime.now(timezone.utc)

            row.last_heartbeat_at = now
            row.updated_at = now
            row.last_error = None

            if installation is not None:
                installation.last_health_check_at = now
                installation.last_error = None
                installation.updated_at = now

                if installation.enabled:
                    installation.status = "enabled"

            await session.commit()

    async def reconcile_running(
        self,
        instance: PluginRuntimeInstance,
    ) -> None:
        key = (instance.guild_id, instance.plugin_key)
        managed = self.processes.get(key)

        if managed is not None:
            process = managed.process

            if process.returncode is None:
                configuration_changed = (
                    managed.generation != instance.generation
                    or managed.package_path
                    != (instance.package_path or "")
                )

                if configuration_changed:
                    logger.info(
                        "Restarting plugin after generation/package change "
                        "plugin_key=%s guild_id=%s",
                        instance.plugin_key,
                        instance.guild_id,
                    )
                    await self.terminate(key, managed)
                    managed = None
                else:
                    loop_time = asyncio.get_running_loop().time()

                    if (
                        loop_time
                        - managed.last_heartbeat_monotonic
                        >= self.heartbeat_seconds
                    ):
                        await self.heartbeat(instance)
                        managed.last_heartbeat_monotonic = loop_time

                    return

            else:
                exit_code = process.returncode
                restart_count = managed.restart_count + 1

                logger.error(
                    "Plugin exited unexpectedly "
                    "plugin_key=%s guild_id=%s "
                    "exit_code=%s restart=%s/%s",
                    instance.plugin_key,
                    instance.guild_id,
                    exit_code,
                    restart_count,
                    self.max_restarts,
                )

                self.processes.pop(key, None)

                if restart_count > self.max_restarts:
                    await self.mark_error_and_stop(
                        instance,
                        (
                            "Plugin exceeded maximum restart count; "
                            f"last exit code: {exit_code}"
                        ),
                    )
                    return

                await asyncio.sleep(
                    min(2 ** restart_count, 30)
                )

                managed = await self.spawn(
                    instance,
                    restart_count=restart_count,
                )
                self.processes[key] = managed
                return

        try:
            managed = await self.spawn(instance)
            self.processes[key] = managed
        except Exception as exc:
            logger.exception(
                "Unable to start plugin plugin_key=%s guild_id=%s",
                instance.plugin_key,
                instance.guild_id,
            )
            await self.mark_error_and_stop(
                instance,
                f"Runtime start failed: {exc}",
            )

    async def reconcile(self) -> None:
        async with AsyncSessionFactory() as session:
            instances = await self.list_instances(session)

        instance_keys = {
            (instance.guild_id, instance.plugin_key)
            for instance in instances
        }

        for key, managed in list(self.processes.items()):
            if key not in instance_keys:
                await self.terminate(key, managed)

        for instance in instances:
            key = (instance.guild_id, instance.plugin_key)

            if instance.state == "running":
                await self.reconcile_running(instance)
                continue

            managed = self.processes.get(key)

            if managed is not None:
                await self.terminate(key, managed)

    async def shutdown(self) -> None:
        logger.info("Stopping all managed plugin processes")

        for key, managed in list(self.processes.items()):
            try:
                await self.terminate(key, managed)
            except Exception:
                logger.exception(
                    "Failed stopping plugin plugin_key=%s guild_id=%s",
                    key[1],
                    key[0],
                )

    async def run(self) -> None:
        logger.info(
            "ShieldNet Plugin Runtime Manager started "
            "poll=%ss heartbeat=%ss "
            "memory=%sMB cpu=%ss files=%s processes=%s",
            self.poll_seconds,
            self.heartbeat_seconds,
            self.sandbox_limits.memory_mb,
            self.sandbox_limits.cpu_seconds,
            self.sandbox_limits.open_files,
            self.sandbox_limits.processes,
        )

        try:
            while True:
                try:
                    await self.reconcile()
                except asyncio.CancelledError:
                    raise
                except Exception:
                    logger.exception("Runtime reconciliation failed")

                await asyncio.sleep(self.poll_seconds)
        finally:
            await self.shutdown()


async def async_main() -> None:
    manager = PluginRuntimeManager()

    try:
        await manager.run()
    finally:
        await close_database()


def main() -> None:
    logging.basicConfig(
        level=os.getenv("LOG_LEVEL", "INFO").upper(),
        format=(
            "%(asctime)s %(levelname)s "
            "%(name)s %(message)s"
        ),
    )

    try:
        asyncio.run(async_main())
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
