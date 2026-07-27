import asyncio
import logging
import os
import shutil
import ssl
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import AsyncSessionFactory, close_database
from app.models.plugins import (
    PluginInstallJob,
    PluginInstallLog,
    PluginMarketplaceItem,
    PluginRuntimeEvent,
    PluginRuntimeState,
)
from app.plugin_worker.config import WorkerSettings
from app.plugin_worker.activation import PluginActivator
from app.plugin_worker.install_journal import recover_install_journals
from app.plugin_worker.security import (
    PackageValidationError,
    load_and_validate_manifest,
    safe_extract_zip,
    sha256_file,
)

logger = logging.getLogger("shieldnet.plugin_worker")


class PluginValidationWorker:
    def __init__(self, settings: WorkerSettings) -> None:
        self.settings = settings
        self.downloads = settings.root / "downloads"
        self.staging = settings.root / "staging"
        self.validated = settings.root / "validated"
        self.quarantine = settings.root / "quarantine"

    def prepare_directories(self) -> None:
        for path in (
            self.settings.root,
            self.downloads,
            self.staging,
            self.validated,
            self.quarantine,
        ):
            path.mkdir(parents=True, exist_ok=True)

    async def claim_job(self, session: AsyncSession) -> PluginInstallJob | None:
        async with session.begin():
            job = (
                await session.execute(
                    select(PluginInstallJob)
                    .where(
                        PluginInstallJob.status == "queued",
                        PluginInstallJob.action.in_(("install", "update")),
                    )
                    .order_by(PluginInstallJob.created_at.asc())
                    .with_for_update(skip_locked=True)
                    .limit(1)
                )
            ).scalar_one_or_none()
            if job is None:
                return None
            job.status = "running"
            job.progress = 5
            job.started_at = datetime.now(timezone.utc)
            session.add(
                PluginInstallLog(
                    job_id=job.id,
                    level="info",
                    message="validation worker claimed job",
                    metadata_json={},
                )
            )
        return job

    async def process_job(self, job_id: UUID) -> None:
        async with AsyncSessionFactory() as session:
            job = (
                await session.execute(
                    select(PluginInstallJob).where(
                        PluginInstallJob.id == job_id
                    )
                )
            ).scalar_one()
            try:
                item = await self._resolve_package(session, job)
                await self._set_status(session, job, "downloading", 15)
                archive_path = await asyncio.to_thread(
                    self._download_package, job, item.package_url
                )

                await self._set_status(session, job, "verifying", 40)
                actual_checksum = await asyncio.to_thread(
                    sha256_file, archive_path
                )
                if actual_checksum.lower() != item.checksum_sha256.lower():
                    raise PackageValidationError("package SHA-256 mismatch")

                extract_path = self.staging / str(job.id)
                shutil.rmtree(extract_path, ignore_errors=True)
                await self._set_status(session, job, "extracting", 55)
                await asyncio.to_thread(
                    safe_extract_zip,
                    archive_path,
                    extract_path,
                    max_uncompressed_bytes=self.settings.max_package_bytes * 4,
                )

                await self._set_status(session, job, "validating", 75)
                manifest = await asyncio.to_thread(
                    load_and_validate_manifest,
                    extract_path,
                    expected_plugin_key=job.plugin_key,
                    expected_version=item.version,
                    allowed_permissions=self.settings.allowed_permissions,
                )

                final_path = self.validated / job.plugin_key / item.version
                final_path.parent.mkdir(parents=True, exist_ok=True)
                if final_path.exists():
                    shutil.rmtree(final_path)
                os.replace(extract_path, final_path)

                await self._record_validated(
                    session, job, item.version, final_path, manifest
                )
                await PluginActivator().activate(
                    session,
                    job=job,
                    validated_path=final_path,
                )
                await self._complete_job(session, job.id)
            except Exception as exc:
                logger.exception("plugin validation job failed: %s", job.id)
                await session.rollback()
                await self._fail_job(session, job.id, str(exc))

    async def _resolve_package(
        self,
        session: AsyncSession,
        job: PluginInstallJob,
    ) -> PluginMarketplaceItem:
        item = (
            await session.execute(
                select(PluginMarketplaceItem).where(
                    PluginMarketplaceItem.plugin_key == job.plugin_key,
                    PluginMarketplaceItem.status == "published",
                    PluginMarketplaceItem.published.is_(True),
                )
            )
        ).scalar_one_or_none()
        if item is None:
            raise PackageValidationError(
                "published Marketplace plugin not found"
            )
        if not item.version or not item.package_url or not item.checksum_sha256:
            raise PackageValidationError("Marketplace package is incomplete")
        if job.requested_version and job.requested_version != item.version:
            raise PackageValidationError(
                "requested version is not the current Marketplace package"
            )
        return item

    def _download_package(
        self, job: PluginInstallJob, package_url: str
    ) -> Path:
        parsed = urllib.parse.urlparse(package_url)
        if parsed.scheme != "https":
            raise PackageValidationError(
                "only HTTPS package URLs are allowed"
            )
        if not parsed.hostname:
            raise PackageValidationError("package URL has no hostname")
        if parsed.username or parsed.password:
            raise PackageValidationError(
                "credentials in package URLs are forbidden"
            )

        target = self.downloads / f"{job.id}.zip"
        temporary = target.with_suffix(".part")
        temporary.unlink(missing_ok=True)
        request = urllib.request.Request(
            package_url,
            headers={"User-Agent": "ShieldNet-Plugin-Validator/2.0"},
        )
        context = ssl.create_default_context()
        written = 0
        try:
            with urllib.request.urlopen(
                request,
                timeout=self.settings.download_timeout_seconds,
                context=context,
            ) as response, temporary.open("wb") as output:
                final_url = urllib.parse.urlparse(response.geturl())
                if final_url.scheme != "https":
                    raise PackageValidationError(
                        "package redirect left HTTPS"
                    )
                content_length = response.headers.get("Content-Length")
                if (
                    content_length
                    and int(content_length) > self.settings.max_package_bytes
                ):
                    raise PackageValidationError(
                        "package exceeds maximum size"
                    )
                while True:
                    chunk = response.read(1024 * 1024)
                    if not chunk:
                        break
                    written += len(chunk)
                    if written > self.settings.max_package_bytes:
                        raise PackageValidationError(
                            "package exceeds maximum size"
                        )
                    output.write(chunk)
        except Exception:
            temporary.unlink(missing_ok=True)
            raise
        os.replace(temporary, target)
        return target

    async def _set_status(
        self,
        session: AsyncSession,
        job: PluginInstallJob,
        status: str,
        progress: int,
    ) -> None:
        job.status = status
        job.progress = progress
        session.add(
            PluginInstallLog(
                job_id=job.id,
                level="info",
                message=f"job status changed to {status}",
                metadata_json={"progress": progress},
            )
        )
        await session.commit()

    async def _record_validated(
        self,
        session: AsyncSession,
        job: PluginInstallJob,
        version: str,
        final_path: Path,
        manifest: dict,
    ) -> None:
        now = datetime.now(timezone.utc)
        await session.execute(
            insert(PluginRuntimeState)
            .values(
                plugin_key=job.plugin_key,
                prepared_version=version,
                package_path=str(final_path),
                manifest_json=manifest,
                state="validated",
                last_job_id=job.id,
                last_error=None,
                updated_at=now,
            )
            .on_conflict_do_update(
                index_elements=[PluginRuntimeState.plugin_key],
                set_={
                    "prepared_version": version,
                    "package_path": str(final_path),
                    "manifest_json": manifest,
                    "state": "validated",
                    "last_job_id": job.id,
                    "last_error": None,
                    "updated_at": now,
                },
            )
        )
        job.status = "validated"
        job.progress = 78
        job.finished_at = None
        session.add(
            PluginInstallLog(
                job_id=job.id,
                level="info",
                message=(
                    "package validated and prepared for activation; "
                    "installation is not complete yet"
                ),
                metadata_json={
                    "path": str(final_path),
                    "version": version,
                },
            )
        )
        session.add(
            PluginRuntimeEvent(
                plugin_key=job.plugin_key,
                job_id=job.id,
                event_type="package_validated",
                message="Plugin package passed validation",
                metadata_json={
                    "version": version,
                    "path": str(final_path),
                },
            )
        )
        await session.commit()

    async def _complete_job(
        self,
        session: AsyncSession,
        job_id: UUID,
    ) -> None:
        job = (
            await session.execute(
                select(PluginInstallJob).where(
                    PluginInstallJob.id == job_id
                )
            )
        ).scalar_one()
        now = datetime.now(timezone.utc)
        job.status = "installed"
        job.progress = 100
        job.error = None
        job.finished_at = now
        session.add(
            PluginInstallLog(
                job_id=job.id,
                level="info",
                message="plugin installation completed",
                metadata_json={"progress": 100},
            )
        )
        session.add(
            PluginRuntimeEvent(
                plugin_key=job.plugin_key,
                job_id=job.id,
                event_type="install_completed",
                message="Plugin installation completed",
                metadata_json={"progress": 100},
            )
        )
        await session.commit()

    async def _fail_job(
        self,
        session: AsyncSession,
        job_id: UUID,
        error: str,
    ) -> None:
        job = (
            await session.execute(
                select(PluginInstallJob).where(
                    PluginInstallJob.id == job_id
                )
            )
        ).scalar_one()
        now = datetime.now(timezone.utc)
        job.status = "failed"
        job.error = error[:8000]
        job.finished_at = now
        session.add(
            PluginInstallLog(
                job_id=job.id,
                level="error",
                message="plugin installation failed",
                metadata_json={"error": error[:4000]},
            )
        )
        session.add(
            PluginRuntimeEvent(
                plugin_key=job.plugin_key,
                job_id=job.id,
                event_type="install_failed",
                message="Plugin installation failed",
                metadata_json={"error": error[:4000]},
            )
        )
        await session.commit()

    async def run(self) -> None:
        self.prepare_directories()
        async with AsyncSessionFactory() as recovery_session:
            reports = await recover_install_journals(recovery_session)
        for report in reports:
            if report.error:
                logger.error(
                    "plugin install recovery failed: %s: %s",
                    report.journal_path,
                    report.error,
                )
            else:
                logger.warning(
                    "plugin install recovery completed: "
                    "plugin=%s stage=%s action=%s",
                    report.plugin_key,
                    report.stage,
                    report.action,
                )
        logger.info("ShieldNet plugin validation worker started")
        while True:
            try:
                async with AsyncSessionFactory() as session:
                    job = await self.claim_job(session)
                if job is None:
                    await asyncio.sleep(self.settings.poll_seconds)
                    continue
                await self.process_job(job.id)
            except asyncio.CancelledError:
                raise
            except Exception:
                logger.exception("worker loop error")
                await asyncio.sleep(self.settings.poll_seconds)


async def async_main() -> None:
    logging.basicConfig(
        level=os.getenv("LOG_LEVEL", "INFO").upper(),
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )
    worker = PluginValidationWorker(WorkerSettings.from_env())
    try:
        await worker.run()
    finally:
        await close_database()


def main() -> None:
    asyncio.run(async_main())


if __name__ == "__main__":
    main()
