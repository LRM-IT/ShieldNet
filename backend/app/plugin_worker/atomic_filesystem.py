from __future__ import annotations

import os
import shutil
from dataclasses import dataclass
from pathlib import Path
from uuid import UUID

from app.plugins.manifest import PluginManifest


class PluginFilesystemCommitError(RuntimeError):
    """Raised when a plugin directory cannot be committed atomically."""


@dataclass(frozen=True)
class PluginFilesystemCommit:
    target: Path
    staging: Path
    displaced: Path
    checksum_sha256: str
    replaced_existing: bool


def fsync_directory(path: Path) -> None:
    descriptor = os.open(path, os.O_RDONLY)
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


def fsync_tree(root: Path) -> None:
    if not root.is_dir():
        raise PluginFilesystemCommitError(
            f"Staging directory does not exist: {root}"
        )

    for item in sorted(root.rglob("*")):
        if item.is_symlink():
            raise PluginFilesystemCommitError(
                f"Plugin staging tree contains a symbolic link: {item}"
            )
        if item.is_file():
            with item.open("rb") as handle:
                os.fsync(handle.fileno())

    directories = [item for item in root.rglob("*") if item.is_dir()]
    for directory in sorted(
        directories,
        key=lambda value: len(value.parts),
        reverse=True,
    ):
        fsync_directory(directory)
    fsync_directory(root)


def prepare_staging(
    *,
    validated_path: Path,
    staging: Path,
    expected_plugin_key: str,
    expected_version: str,
    checksum_function,
) -> str:
    shutil.rmtree(staging, ignore_errors=True)
    shutil.copytree(validated_path, staging)

    copied_manifest = PluginManifest.from_path(staging / "plugin.json")
    if copied_manifest.plugin_key != expected_plugin_key:
        raise PluginFilesystemCommitError(
            "Copied package plugin key mismatch"
        )
    if copied_manifest.version != expected_version:
        raise PluginFilesystemCommitError(
            "Copied package version mismatch"
        )

    source_checksum = checksum_function(validated_path)
    staging_checksum = checksum_function(staging)
    if source_checksum != staging_checksum:
        raise PluginFilesystemCommitError(
            "Staging checksum does not match validated package checksum"
        )

    fsync_tree(staging)
    return staging_checksum


def atomic_commit(
    *,
    target: Path,
    staging: Path,
    job_id: UUID,
    checksum_sha256: str,
    checksum_function,
) -> PluginFilesystemCommit:
    target.parent.mkdir(parents=True, exist_ok=True)
    fsync_directory(target.parent)

    displaced = target.parent / f".{target.name}.displaced-{job_id}"
    shutil.rmtree(displaced, ignore_errors=True)
    replaced_existing = target.exists()

    try:
        if replaced_existing:
            os.replace(target, displaced)
            fsync_directory(target.parent)

        os.replace(staging, target)
        fsync_directory(target.parent)

        committed_checksum = checksum_function(target)
        if committed_checksum != checksum_sha256:
            raise PluginFilesystemCommitError(
                "Committed plugin checksum does not match staged checksum"
            )

        PluginManifest.from_path(target / "plugin.json")
        return PluginFilesystemCommit(
            target=target,
            staging=staging,
            displaced=displaced,
            checksum_sha256=committed_checksum,
            replaced_existing=replaced_existing,
        )
    except Exception:
        shutil.rmtree(target, ignore_errors=True)
        if displaced.exists():
            os.replace(displaced, target)
        fsync_directory(target.parent)
        raise


def finalize_commit(commit: PluginFilesystemCommit) -> None:
    shutil.rmtree(commit.displaced, ignore_errors=True)
    fsync_directory(commit.target.parent)


def rollback_commit(commit: PluginFilesystemCommit) -> None:
    shutil.rmtree(commit.staging, ignore_errors=True)
    shutil.rmtree(commit.target, ignore_errors=True)
    if commit.displaced.exists():
        os.replace(commit.displaced, commit.target)
    fsync_directory(commit.target.parent)
