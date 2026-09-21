from fastapi import APIRouter, Request

from app.services.visitor_locale import country_for_ip


router = APIRouter(tags=["Public locale"])


@router.get("/public/locale")
async def detect_public_locale(request: Request) -> dict[str, str | bool]:
    forwarded_ip = request.headers.get("cf-connecting-ip") or request.headers.get("x-real-ip")
    client_ip = forwarded_ip or (request.client.host if request.client else None)
    country_code = country_for_ip(client_ip)

    # Cloudflare's country header is a safe fallback when the local database cannot
    # classify an address. The local GeoLite database remains the primary source.
    if country_code is None:
        header_country = request.headers.get("cf-ipcountry", "").strip().upper()
        country_code = header_country if len(header_country) == 2 else ""

    return {
        "country_code": country_code or "",
        "recommended_locale": "uk" if country_code == "UA" else "en",
        "is_ukraine": country_code == "UA",
    }
