from __future__ import annotations

import asyncio
import inspect
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import StrEnum
from typing import Any, Awaitable, Callable, Protocol


class PluginRuntimeError(RuntimeError):
    """Raised when a plugin runtime lifecycle operation fails."""


class PluginRuntimeStateName(StrEnum):
    INSTALLED = "installed"
    STARTING = "starting"
    RUNNING = "running"
    STOPPING = "stopping"
    STOPPED = "stopped"
    FAILED = "failed"


class PluginRuntimeAdapter(Protocol):
    async def start(self) -> None: ...

    async def stop(self) -> None: ...

    async def health(self) -> dict[str, Any]: ...


StateListener = Callable[
    ["PluginRuntimeSnapshot"],
    Awaitable[None] | None,
]


@dataclass(frozen=True)
class PluginRuntimeSnapshot:
    plugin_key: str
    version: str
    state: PluginRuntimeStateName
    healthy: bool
    started_at: datetime | None
    stopped_at: datetime | None
    updated_at: datetime
    uptime_seconds: float
    start_count: int
    stop_count: int
    failure_count: int
    last_error: str | None
    health: dict[str, Any]


@dataclass
class _PluginRuntimeEntry:
    plugin_key: str
    version: str
    adapter: PluginRuntimeAdapter
    state: PluginRuntimeStateName = PluginRuntimeStateName.INSTALLED
    healthy: bool = False
    started_at: datetime | None = None
    stopped_at: datetime | None = None
    updated_at: datetime = field(
        default_factory=lambda: datetime.now(timezone.utc)
    )
    start_count: int = 0
    stop_count: int = 0
    failure_count: int = 0
    last_error: str | None = None
    health_data: dict[str, Any] = field(default_factory=dict)
    monotonic_started_at: float | None = None


class PluginRuntimeManager:
    """
    In-process plugin lifecycle coordinator.

    This core does not import plugin code dynamically, register HTTP routes,
    write database records, or apply migrations. Those integrations are
    intentionally delegated to later stages.
    """

    def __init__(self) -> None:
        self._entries: dict[str, _PluginRuntimeEntry] = {}
        self._locks: dict[str, asyncio.Lock] = {}
        self._listeners: list[StateListener] = []
        self._registry_lock = asyncio.Lock()

    async def register(
        self,
        *,
        plugin_key: str,
        version: str,
        adapter: PluginRuntimeAdapter,
        replace: bool = False,
    ) -> PluginRuntimeSnapshot:
        key = self._normalize_plugin_key(plugin_key)
        version_value = version.strip()
        if not version_value:
            raise PluginRuntimeError("Plugin version must not be empty")

        self._validate_adapter(adapter)

        async with self._registry_lock:
            existing = self._entries.get(key)
            if existing is not None and not replace:
                raise PluginRuntimeError(
                    f"Plugin runtime is already registered: {key}"
                )
            if (
                existing is not None
                and existing.state
                in {
                    PluginRuntimeStateName.STARTING,
                    PluginRuntimeStateName.RUNNING,
                    PluginRuntimeStateName.STOPPING,
                }
            ):
                raise PluginRuntimeError(
                    f"Cannot replace active plugin runtime: {key}"
                )

            entry = _PluginRuntimeEntry(
                plugin_key=key,
                version=version_value,
                adapter=adapter,
            )
            self._entries[key] = entry
            self._locks.setdefault(key, asyncio.Lock())

        snapshot = self._snapshot(entry)
        await self._notify(snapshot)
        return snapshot

    async def unregister(self, plugin_key: str) -> None:
        key = self._normalize_plugin_key(plugin_key)
        lock = self._lock_for(key)

        async with lock:
            entry = self._require_entry(key)
            if entry.state in {
                PluginRuntimeStateName.STARTING,
                PluginRuntimeStateName.RUNNING,
                PluginRuntimeStateName.STOPPING,
            }:
                raise PluginRuntimeError(
                    f"Stop plugin runtime before unregistering: {key}"
                )

            async with self._registry_lock:
                self._entries.pop(key, None)
                self._locks.pop(key, None)

    async def start(self, plugin_key: str) -> PluginRuntimeSnapshot:
        key = self._normalize_plugin_key(plugin_key)
        lock = self._lock_for(key)

        async with lock:
            entry = self._require_entry(key)

            if entry.state == PluginRuntimeStateName.RUNNING:
                return self._snapshot(entry)
            if entry.state in {
                PluginRuntimeStateName.STARTING,
                PluginRuntimeStateName.STOPPING,
            }:
                raise PluginRuntimeError(
                    f"Plugin runtime is busy: {key} ({entry.state})"
                )

            await self._transition(
                entry,
                PluginRuntimeStateName.STARTING,
                healthy=False,
                error=None,
            )

            try:
                await entry.adapter.start()
            except Exception as exc:
                entry.failure_count += 1
                await self._transition(
                    entry,
                    PluginRuntimeStateName.FAILED,
                    healthy=False,
                    error=str(exc),
                )
                raise PluginRuntimeError(
                    f"Plugin runtime start failed: {key}: {exc}"
                ) from exc

            now = datetime.now(timezone.utc)
            entry.started_at = now
            entry.stopped_at = None
            entry.monotonic_started_at = time.monotonic()
            entry.start_count += 1
            entry.health_data = {}
            return await self._transition(
                entry,
                PluginRuntimeStateName.RUNNING,
                healthy=True,
                error=None,
            )

    async def stop(self, plugin_key: str) -> PluginRuntimeSnapshot:
        key = self._normalize_plugin_key(plugin_key)
        lock = self._lock_for(key)

        async with lock:
            entry = self._require_entry(key)

            if entry.state in {
                PluginRuntimeStateName.INSTALLED,
                PluginRuntimeStateName.STOPPED,
            }:
                return self._snapshot(entry)
            if entry.state == PluginRuntimeStateName.STARTING:
                raise PluginRuntimeError(
                    f"Plugin runtime is still starting: {key}"
                )
            if entry.state == PluginRuntimeStateName.STOPPING:
                return self._snapshot(entry)

            await self._transition(
                entry,
                PluginRuntimeStateName.STOPPING,
                healthy=False,
                error=entry.last_error,
            )

            try:
                await entry.adapter.stop()
            except Exception as exc:
                entry.failure_count += 1
                await self._transition(
                    entry,
                    PluginRuntimeStateName.FAILED,
                    healthy=False,
                    error=str(exc),
                )
                raise PluginRuntimeError(
                    f"Plugin runtime stop failed: {key}: {exc}"
                ) from exc

            entry.stopped_at = datetime.now(timezone.utc)
            entry.monotonic_started_at = None
            entry.stop_count += 1
            entry.health_data = {}
            return await self._transition(
                entry,
                PluginRuntimeStateName.STOPPED,
                healthy=False,
                error=None,
            )

    async def restart(self, plugin_key: str) -> PluginRuntimeSnapshot:
        key = self._normalize_plugin_key(plugin_key)
        current = self._require_entry(key)
        if current.state == PluginRuntimeStateName.RUNNING:
            await self.stop(key)
        return await self.start(key)

    async def check_health(
        self,
        plugin_key: str,
    ) -> PluginRuntimeSnapshot:
        key = self._normalize_plugin_key(plugin_key)
        lock = self._lock_for(key)

        async with lock:
            entry = self._require_entry(key)
            if entry.state != PluginRuntimeStateName.RUNNING:
                entry.healthy = False
                entry.health_data = {
                    "status": "not_running",
                    "state": entry.state.value,
                }
                entry.updated_at = datetime.now(timezone.utc)
                snapshot = self._snapshot(entry)
                await self._notify(snapshot)
                return snapshot

            try:
                result = await entry.adapter.health()
                if not isinstance(result, dict):
                    raise TypeError(
                        "Plugin runtime health() must return a dictionary"
                    )
            except Exception as exc:
                entry.failure_count += 1
                entry.healthy = False
                entry.last_error = str(exc)
                entry.health_data = {
                    "status": "error",
                    "error": str(exc),
                }
            else:
                entry.health_data = dict(result)
                status = str(result.get("status", "ok")).lower()
                entry.healthy = status in {"ok", "healthy", "ready"}
                if entry.healthy:
                    entry.last_error = None

            entry.updated_at = datetime.now(timezone.utc)
            snapshot = self._snapshot(entry)
            await self._notify(snapshot)
            return snapshot

    def get(self, plugin_key: str) -> PluginRuntimeSnapshot:
        key = self._normalize_plugin_key(plugin_key)
        return self._snapshot(self._require_entry(key))

    def list(self) -> tuple[PluginRuntimeSnapshot, ...]:
        return tuple(
            self._snapshot(self._entries[key])
            for key in sorted(self._entries)
        )

    def add_listener(self, listener: StateListener) -> None:
        if listener not in self._listeners:
            self._listeners.append(listener)

    def remove_listener(self, listener: StateListener) -> None:
        if listener in self._listeners:
            self._listeners.remove(listener)

    async def shutdown(self) -> tuple[PluginRuntimeSnapshot, ...]:
        results: list[PluginRuntimeSnapshot] = []
        for key in sorted(self._entries):
            entry = self._entries[key]
            if entry.state in {
                PluginRuntimeStateName.RUNNING,
                PluginRuntimeStateName.FAILED,
            }:
                try:
                    results.append(await self.stop(key))
                except PluginRuntimeError:
                    results.append(self.get(key))
        return tuple(results)

    async def _transition(
        self,
        entry: _PluginRuntimeEntry,
        state: PluginRuntimeStateName,
        *,
        healthy: bool,
        error: str | None,
    ) -> PluginRuntimeSnapshot:
        entry.state = state
        entry.healthy = healthy
        entry.last_error = error
        entry.updated_at = datetime.now(timezone.utc)
        snapshot = self._snapshot(entry)
        await self._notify(snapshot)
        return snapshot

    async def _notify(self, snapshot: PluginRuntimeSnapshot) -> None:
        for listener in tuple(self._listeners):
            try:
                result = listener(snapshot)
                if inspect.isawaitable(result):
                    await result
            except Exception:
                # Observers must never break runtime state transitions.
                continue

    def _snapshot(
        self,
        entry: _PluginRuntimeEntry,
    ) -> PluginRuntimeSnapshot:
        uptime = 0.0
        if entry.monotonic_started_at is not None:
            uptime = max(
                0.0,
                time.monotonic() - entry.monotonic_started_at,
            )

        return PluginRuntimeSnapshot(
            plugin_key=entry.plugin_key,
            version=entry.version,
            state=entry.state,
            healthy=entry.healthy,
            started_at=entry.started_at,
            stopped_at=entry.stopped_at,
            updated_at=entry.updated_at,
            uptime_seconds=uptime,
            start_count=entry.start_count,
            stop_count=entry.stop_count,
            failure_count=entry.failure_count,
            last_error=entry.last_error,
            health=dict(entry.health_data),
        )

    def _require_entry(self, plugin_key: str) -> _PluginRuntimeEntry:
        entry = self._entries.get(plugin_key)
        if entry is None:
            raise PluginRuntimeError(
                f"Plugin runtime is not registered: {plugin_key}"
            )
        return entry

    def _lock_for(self, plugin_key: str) -> asyncio.Lock:
        lock = self._locks.get(plugin_key)
        if lock is None:
            raise PluginRuntimeError(
                f"Plugin runtime is not registered: {plugin_key}"
            )
        return lock

    @staticmethod
    def _normalize_plugin_key(plugin_key: str) -> str:
        key = plugin_key.strip().lower()
        if not key:
            raise PluginRuntimeError("Plugin key must not be empty")
        if any(
            not (
                character.isascii()
                and (
                    character.islower()
                    or character.isdigit()
                    or character in {"-", "_"}
                )
            )
            for character in key
        ):
            raise PluginRuntimeError(
                f"Invalid plugin key: {plugin_key}"
            )
        return key

    @staticmethod
    def _validate_adapter(adapter: PluginRuntimeAdapter) -> None:
        for method_name in ("start", "stop", "health"):
            method = getattr(adapter, method_name, None)
            if method is None or not callable(method):
                raise PluginRuntimeError(
                    f"Plugin runtime adapter is missing "
                    f"{method_name}()"
                )
