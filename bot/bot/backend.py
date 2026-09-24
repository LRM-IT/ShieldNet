import httpx
from bot.config import settings


class BackendAPIError(RuntimeError):
    """A normalized error returned by the ShieldNet backend."""

    def __init__(self, message: str, *, status_code: int | None = None) -> None:
        super().__init__(message)
        self.status_code = status_code


class BackendClient:
    def __init__(self) -> None:
        self.base_url = settings.backend_url.rstrip("/")
        self.headers = {
            "X-ShieldNet-Service-Token": settings.internal_service_token,
            "Content-Type": "application/json",
        }

    async def register_guild(self, guild) -> None:
        payload = {
            "guild_id": guild.id,
            "name": guild.name,
            "icon_url": str(guild.icon.url) if guild.icon else None,
            "owner_discord_id": guild.owner_id,
            "member_count": guild.member_count or 0,
            "preferred_language": settings.default_language,
        }
        async with httpx.AsyncClient(timeout=20) as client:
            response = await client.post(
                f"{self.base_url}/api/v1/internal/discord/guilds/register",
                headers=self.headers,
                json=payload,
            )
        response.raise_for_status()

    async def mark_guild_left(self, guild_id: int) -> None:
        async with httpx.AsyncClient(timeout=20) as client:
            response = await client.post(
                f"{self.base_url}/api/v1/internal/discord/guilds/left",
                headers=self.headers,
                json={"guild_id": guild_id},
            )
        response.raise_for_status()

    async def reconcile_guilds(self, guild_ids: list[int]) -> None:
        async with httpx.AsyncClient(timeout=20) as client:
            response = await client.post(
                f"{self.base_url}/api/v1/internal/discord/guilds/reconcile",
                headers=self.headers,
                json={"guild_ids": guild_ids},
            )
        response.raise_for_status()

    async def get_guild_modules(self, guild_id: int) -> dict:
        async with httpx.AsyncClient(timeout=20) as client:
            response = await client.get(
                f"{self.base_url}/api/v1/internal/modules/guilds/{guild_id}",
                headers=self.headers,
            )
        response.raise_for_status()
        return response.json()

    async def execute_ai(
        self,
        *,
        guild_id: int,
        module_key: str,
        capability: str,
        input_text: str,
        source_language: str | None = None,
        target_language: str | None = None,
        system_prompt: str | None = None,
        metadata: dict | None = None,
    ) -> dict:
        payload = {
            "guild_id": guild_id,
            "module_key": module_key,
            "capability": capability,
            "input_text": input_text,
            "source_language": source_language,
            "target_language": target_language,
            "system_prompt": system_prompt,
            "metadata": metadata or {},
        }
        try:
            async with httpx.AsyncClient(timeout=60) as client:
                response = await client.post(
                    f"{self.base_url}/api/v1/internal/ai/execute",
                    headers=self.headers,
                    json=payload,
                )
        except httpx.TimeoutException as exc:
            raise BackendAPIError("AI service request timed out.") from exc
        except httpx.RequestError as exc:
            raise BackendAPIError("ShieldNet backend is unavailable.") from exc

        if response.is_error:
            detail = None
            try:
                body = response.json()
                detail = body.get("detail") if isinstance(body, dict) else None
            except ValueError:
                detail = None
            raise BackendAPIError(
                str(detail or f"AI service returned HTTP {response.status_code}."),
                status_code=response.status_code,
            )
        return response.json()

    async def heartbeat(self, *, worker_name: str, worker_type: str, status: str, metadata: dict | None = None) -> None:
        payload = {
            "worker_name": worker_name,
            "worker_type": worker_type,
            "status": status,
            "metadata": metadata or {},
        }
        async with httpx.AsyncClient(timeout=10) as client:
            response = await client.post(
                f"{self.base_url}/api/v1/internal/runtime/heartbeat",
                headers=self.headers,
                json=payload,
            )
        response.raise_for_status()
