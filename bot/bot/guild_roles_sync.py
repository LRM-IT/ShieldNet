import httpx
from bot.config import settings

class GuildRoleSyncClient:
    def __init__(self, bot):
        self.bot = bot
        self.base_url = settings.backend_url.rstrip("/")
        self.headers = {"X-ShieldNet-Service-Token": settings.internal_service_token}

    async def synchronize(self, guild):
        bot_member = guild.me
        roles = []
        for role in await guild.fetch_roles():
            if role.is_default():
                continue
            roles.append({
                "discord_role_id": role.id,
                "name": role.name,
                "position": role.position,
                "color": role.color.value,
                "permissions": role.permissions.value,
                "managed": role.managed,
                "assignable": bool(bot_member and not role.managed and role < bot_member.top_role),
            })
        async with httpx.AsyncClient(timeout=30) as client:
            response = await client.post(
                f"{self.base_url}/api/v1/internal/discord/guilds/{guild.id}/roles/sync",
                headers=self.headers,
                json={"roles": roles},
            )
        response.raise_for_status()
        return response.json().get("count", len(roles))
