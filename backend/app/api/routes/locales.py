import json
from pathlib import Path
from fastapi import APIRouter, HTTPException, status

router = APIRouter(prefix="/locales", tags=["Locales"])
LOCALES_DIR = Path(__file__).resolve().parents[2] / "locales"

def _load(path: Path) -> dict:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Invalid locale file: {path.name}",
        ) from exc

@router.get("")
async def list_locales() -> list[dict]:
    result = []
    for path in sorted(LOCALES_DIR.glob("*.json")):
        data = _load(path)
        language = data.get("_language")
        if isinstance(language, dict) and language.get("code"):
            result.append(language)
    return result

@router.get("/{code}")
async def get_locale(code: str) -> dict:
    safe = code.lower().replace("_", "-").split("-", 1)[0]
    path = LOCALES_DIR / f"{safe}.json"
    if not path.is_file():
        path = LOCALES_DIR / "en.json"
    return _load(path)
