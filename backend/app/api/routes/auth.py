from fastapi import APIRouter, Depends, Request, Response, status
from urllib.parse import urlencode
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy.ext.asyncio import AsyncSession
import json

from app.api.dependencies.auth import get_current_user
from app.core.config import settings
from app.db.session import get_db_session
from app.models.core import User
from app.schemas.auth import LoginRequest, RefreshRequest, TokenPair
from app.schemas.users import user_to_response
from app.services.auth import AuthService
from app.services.discord_oauth import DiscordOAuthService

router = APIRouter(prefix="/auth", tags=["Authentication"])


@router.post("/login", response_model=TokenPair, include_in_schema=False)
async def login(
    payload: LoginRequest,
    request: Request,
    session: AsyncSession = Depends(get_db_session),
) -> TokenPair:
    return await AuthService(session).login(
        payload.identity,
        payload.password,
        request.client.host if request.client else None,
        request.headers.get("user-agent"),
    )


@router.post("/platform/login", response_model=TokenPair)
async def platform_login(
    payload: LoginRequest, request: Request, session: AsyncSession = Depends(get_db_session),
) -> TokenPair:
    return await AuthService(session).platform_login(
        payload.identity, payload.password,
        request.client.host if request.client else None,
        request.headers.get("user-agent"),
    )


@router.post("/refresh", response_model=TokenPair)
async def refresh(
    payload: RefreshRequest,
    request: Request,
    session: AsyncSession = Depends(get_db_session),
) -> TokenPair:
    return await AuthService(session).refresh(
        payload.refresh_token,
        request.client.host if request.client else None,
        request.headers.get("user-agent"),
    )


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
async def logout(
    payload: RefreshRequest,
    session: AsyncSession = Depends(get_db_session),
) -> Response:
    await AuthService(session).logout(payload.refresh_token)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/me")
async def me(current_user: User = Depends(get_current_user)) -> dict:
    payload = user_to_response(current_user)
    payload["auth_source"] = getattr(current_user, "_auth_source", "discord_guild")
    payload["platform_context"] = payload["auth_source"] in {"local_platform", "discord_platform"}
    return payload





@router.get("/discord/bot-install")
async def discord_bot_install(guild_id: int) -> RedirectResponse:
    query = urlencode(
        {
            "client_id": settings.discord_client_id,
            "scope": "bot applications.commands",
            "permissions": str(getattr(settings, "discord_bot_permissions", 8)),
            "guild_id": str(guild_id),
            "disable_guild_select": "true",
        }
    )
    return RedirectResponse(
        url=f"https://discord.com/oauth2/authorize?{query}",
        status_code=status.HTTP_307_TEMPORARY_REDIRECT,
    )

@router.get("/discord/start")
async def discord_start(response: Response) -> dict[str, str]:
    service = DiscordOAuthService()
    state = service.create_state()

    response.set_cookie(
        key="shieldnet_discord_oauth_state",
        value=state,
        max_age=600,
        httponly=True,
        secure=True,
        samesite="lax",
        path="/api/v1/auth/discord",
    )

    return {"authorization_url": service.build_authorization_url(state)}


@router.get("/discord/callback", response_class=HTMLResponse)
async def discord_callback(
    code: str,
    state: str,
    request: Request,
    session: AsyncSession = Depends(get_db_session),
) -> HTMLResponse:
    service = DiscordOAuthService(session)
    service.verify_state(
        state,
        request.cookies.get("shieldnet_discord_oauth_state"),
    )

    tokens = await service.authenticate(
        code,
        request.client.host if request.client else None,
        request.headers.get("user-agent"),
    )

    payload = json.dumps(
        {
            "type": "shieldnet-oauth-result",
            "tokens": tokens.model_dump(),
        }
    )

    html = f"""<!doctype html>
<html>
<head>
  <meta charset="utf-8">
  <title>ShieldNet Login</title>
</head>
<body style="font-family:system-ui;background:#080c17;color:#fff;display:grid;place-items:center;min-height:100vh">
  <div>Authorization complete. This window will close.</div>
  <script>
    if (window.opener) {{
      window.opener.postMessage({payload}, window.location.origin);
      window.close();
    }} else {{
      document.body.innerHTML = '<div>Return to the ShieldNet window.</div>';
    }}
  </script>
</body>
</html>"""

    response = HTMLResponse(content=html)
    response.delete_cookie(
        "shieldnet_discord_oauth_state",
        path="/api/v1/auth/discord",
    )
    return response
