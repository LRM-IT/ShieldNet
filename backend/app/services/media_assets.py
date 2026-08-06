from __future__ import annotations
import re
import shutil
from pathlib import Path
from uuid import UUID
from fastapi import HTTPException, UploadFile
from PIL import Image

ALLOWED_TYPES = {
    "image/png", "image/jpeg", "image/webp", "image/gif",
    "font/ttf", "font/otf", "application/font-sfnt",
}
MAX_SIZE = 30 * 1024 * 1024

class MediaAssetStorage:
    def __init__(self, root: str = "/var/lib/shieldnet/media-assets"):
        self.root = Path(root)

    @staticmethod
    def safe_key(value: str) -> str:
        value = re.sub(r"[^a-z0-9._-]+", "-", value.strip().lower()).strip("-")
        if not value:
            raise HTTPException(422, "Invalid asset key.")
        return value[:140]

    async def save(self, asset_id: UUID, upload: UploadFile, kind: str = "asset") -> tuple[str, int, int | None, int | None]:
        if upload.content_type not in ALLOWED_TYPES:
            raise HTTPException(422, "Unsupported asset format.")
        suffix = Path(upload.filename or "").suffix.lower() or ".bin"
        target_dir = self.root / str(asset_id)
        target_dir.mkdir(parents=True, exist_ok=True)
        target = target_dir / f"{kind}{suffix}"
        size = 0
        with target.open("wb") as handle:
            while chunk := await upload.read(1024 * 1024):
                size += len(chunk)
                if size > MAX_SIZE:
                    target.unlink(missing_ok=True)
                    raise HTTPException(413, "Asset exceeds 30 MB.")
                handle.write(chunk)

        width = height = None
        if upload.content_type.startswith("image/"):
            try:
                with Image.open(target) as image:
                    width, height = image.size
            except Exception:
                pass
        return str(target), size, width, height

    def delete(self, asset_id: UUID) -> None:
        shutil.rmtree(self.root / str(asset_id), ignore_errors=True)
