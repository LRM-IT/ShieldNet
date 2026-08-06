from __future__ import annotations

import json
import re
import shutil
from pathlib import Path
from uuid import UUID

from fastapi import HTTPException, UploadFile

ALLOWED_IMAGE_TYPES = {"image/png", "image/jpeg", "image/webp"}
MAX_IMAGE_SIZE = 20 * 1024 * 1024


class TemplateStorage:
    def __init__(self, root: str = "/var/lib/shieldnet/templates"):
        self.root = Path(root)

    @staticmethod
    def safe_key(value: str) -> str:
        value = re.sub(r"[^a-z0-9._-]+", "-", value.strip().lower()).strip("-")
        if not value:
            raise HTTPException(422, "Template key is invalid.")
        return value[:120]

    async def save_image(self, template_id: UUID, version: int, kind: str, upload: UploadFile) -> str:
        if upload.content_type not in ALLOWED_IMAGE_TYPES:
            raise HTTPException(422, f"{kind} must be PNG, JPEG or WebP.")
        suffix = {"image/png": ".png", "image/jpeg": ".jpg", "image/webp": ".webp"}[upload.content_type]
        target_dir = self.root / str(template_id) / f"v{version}"
        target_dir.mkdir(parents=True, exist_ok=True)
        target = target_dir / f"{kind}{suffix}"
        size = 0
        with target.open("wb") as handle:
            while chunk := await upload.read(1024 * 1024):
                size += len(chunk)
                if size > MAX_IMAGE_SIZE:
                    target.unlink(missing_ok=True)
                    raise HTTPException(413, f"{kind} exceeds 20 MB.")
                handle.write(chunk)
        return str(target)

    def delete_template(self, template_id: UUID) -> None:
        shutil.rmtree(self.root / str(template_id), ignore_errors=True)

    @staticmethod
    def validate_manifest(raw: str, width: int, height: int) -> dict:
        try:
            manifest = json.loads(raw or "{}")
        except json.JSONDecodeError as exc:
            raise HTTPException(422, f"Invalid manifest JSON: {exc.msg}") from exc
        if not isinstance(manifest, dict):
            raise HTTPException(422, "Manifest must be a JSON object.")
        manifest.setdefault("schema_version", 1)
        manifest.setdefault("canvas", {"width": width, "height": height})
        manifest.setdefault("fields", {})
        if not isinstance(manifest["fields"], dict):
            raise HTTPException(422, "manifest.fields must be an object.")
        return manifest
