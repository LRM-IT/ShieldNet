from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, Mapping

from app.plugins.manifest import PluginManifest, Version


class PluginDependencyError(RuntimeError):
    """Raised when plugin dependencies cannot be resolved."""


@dataclass(frozen=True)
class DependencyResolution:
    load_order: tuple[str, ...]
    unload_order: tuple[str, ...]
    graph: dict[str, tuple[str, ...]]


class PluginDependencyResolver:
    def resolve(
        self,
        manifests: Iterable[PluginManifest],
    ) -> DependencyResolution:
        indexed: dict[str, PluginManifest] = {}

        for manifest in manifests:
            if manifest.plugin_key in indexed:
                raise PluginDependencyError(
                    f"Duplicate plugin manifest: {manifest.plugin_key}"
                )
            indexed[manifest.plugin_key] = manifest

        graph: dict[str, tuple[str, ...]] = {}
        for plugin_key, manifest in indexed.items():
            dependencies: list[str] = []
            for dependency_key, minimum_version in manifest.dependencies.items():
                dependency = indexed.get(dependency_key)
                if dependency is None:
                    raise PluginDependencyError(
                        f"{plugin_key} requires missing plugin "
                        f"{dependency_key}"
                    )

                if minimum_version is not None:
                    installed = Version.parse(
                        dependency.version,
                        field_name=f"{dependency_key}.version",
                    )
                    required = Version.parse(
                        minimum_version,
                        field_name=(
                            f"{plugin_key}.dependencies."
                            f"{dependency_key}"
                        ),
                    )
                    if installed < required:
                        raise PluginDependencyError(
                            f"{plugin_key} requires {dependency_key}>="
                            f"{minimum_version}, found "
                            f"{dependency.version}"
                        )

                dependencies.append(dependency_key)

            graph[plugin_key] = tuple(sorted(dependencies))

        load_order = self._topological_sort(graph)
        return DependencyResolution(
            load_order=load_order,
            unload_order=tuple(reversed(load_order)),
            graph=graph,
        )

    def resolve_selected(
        self,
        manifests: Mapping[str, PluginManifest],
        selected: Iterable[str],
    ) -> DependencyResolution:
        required: set[str] = set()
        visiting: set[str] = set()

        def collect(plugin_key: str) -> None:
            if plugin_key in required:
                return
            if plugin_key in visiting:
                raise PluginDependencyError(
                    f"Cyclic dependency detected at {plugin_key}"
                )

            manifest = manifests.get(plugin_key)
            if manifest is None:
                raise PluginDependencyError(
                    f"Selected plugin is unavailable: {plugin_key}"
                )

            visiting.add(plugin_key)
            for dependency_key in manifest.dependencies:
                collect(dependency_key)
            visiting.remove(plugin_key)
            required.add(plugin_key)

        for raw_key in selected:
            collect(raw_key.strip().lower())

        return self.resolve(
            manifests[key]
            for key in sorted(required)
        )

    @staticmethod
    def _topological_sort(
        graph: Mapping[str, tuple[str, ...]],
    ) -> tuple[str, ...]:
        temporary: set[str] = set()
        permanent: set[str] = set()
        result: list[str] = []
        stack: list[str] = []

        def visit(node: str) -> None:
            if node in permanent:
                return
            if node in temporary:
                try:
                    cycle_start = stack.index(node)
                except ValueError:
                    cycle_start = 0
                cycle = stack[cycle_start:] + [node]
                raise PluginDependencyError(
                    "Cyclic dependency: " + " -> ".join(cycle)
                )

            temporary.add(node)
            stack.append(node)
            for dependency in graph.get(node, ()):
                visit(dependency)
            stack.pop()
            temporary.remove(node)
            permanent.add(node)
            result.append(node)

        for node in sorted(graph):
            visit(node)

        return tuple(result)
