from __future__ import annotations

import asyncio
from dataclasses import dataclass
from datetime import datetime, timezone

from app.plugin_worker.runtime_manager import (
    PluginRuntimeManager,
    PluginRuntimeSnapshot,
)


@dataclass(frozen=True)
class RuntimeHealthCycle:
    started_at: datetime
    finished_at: datetime
    checked: int
    healthy: int
    unhealthy: int
    snapshots: tuple[PluginRuntimeSnapshot, ...]


class PluginRuntimeHealthMonitor:
    def __init__(
        self,
        manager: PluginRuntimeManager,
        *,
        interval_seconds: float = 30.0,
    ) -> None:
        if interval_seconds <= 0:
            raise ValueError(
                "Health interval must be greater than zero"
            )
        self.manager = manager
        self.interval_seconds = interval_seconds
        self._task: asyncio.Task[None] | None = None
        self._stop_event = asyncio.Event()
        self.last_cycle: RuntimeHealthCycle | None = None

    @property
    def running(self) -> bool:
        return self._task is not None and not self._task.done()

    async def check_once(self) -> RuntimeHealthCycle:
        started = datetime.now(timezone.utc)
        snapshots: list[PluginRuntimeSnapshot] = []

        for current in self.manager.list():
            snapshots.append(
                await self.manager.check_health(
                    current.plugin_key
                )
            )

        finished = datetime.now(timezone.utc)
        healthy = sum(
            1 for snapshot in snapshots if snapshot.healthy
        )
        cycle = RuntimeHealthCycle(
            started_at=started,
            finished_at=finished,
            checked=len(snapshots),
            healthy=healthy,
            unhealthy=len(snapshots) - healthy,
            snapshots=tuple(snapshots),
        )
        self.last_cycle = cycle
        return cycle

    async def start(self) -> None:
        if self.running:
            return
        self._stop_event.clear()
        self._task = asyncio.create_task(
            self._run(),
            name="shieldnet-plugin-health-monitor",
        )

    async def stop(self) -> None:
        if self._task is None:
            return
        self._stop_event.set()
        await self._task
        self._task = None

    async def _run(self) -> None:
        while not self._stop_event.is_set():
            await self.check_once()
            try:
                await asyncio.wait_for(
                    self._stop_event.wait(),
                    timeout=self.interval_seconds,
                )
            except TimeoutError:
                continue
