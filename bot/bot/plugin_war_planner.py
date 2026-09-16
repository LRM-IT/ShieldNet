from __future__ import annotations

from datetime import datetime

import discord
import httpx

from bot.config import settings


class WarPlanView(discord.ui.View):
    def __init__(self, war: dict):
        super().__init__(timeout=None)
        waves = war.get("waves") or []
        if waves:
            options = []
            assignments = war.get("assignments") or {}
            for wave in waves[:25]:
                used = sum(value == wave["id"] for value in assignments.values())
                capacity = f"/{wave['capacity']}" if wave.get("capacity") else ""
                options.append(discord.SelectOption(label=wave["name"][:100], value=wave["id"], description=f"{used}{capacity} assigned"))
            self.add_item(discord.ui.Select(placeholder="Choose your war wave", options=options, custom_id=f"gc-war:{war['id']}:wave"))
        self.add_item(discord.ui.Button(label="Leave plan", style=discord.ButtonStyle.secondary, emoji="✖", custom_id=f"gc-war:{war['id']}:leave"))


class WarPlanner:
    def __init__(self, bot):
        self.bot = bot
        self.base = settings.backend_url.rstrip("/") + "/api/v1/internal/plugin-war-planner"
        self.headers = {"X-ShieldNet-Service-Token": settings.internal_service_token}

    async def request(self, method: str, path: str, **kwargs):
        async with httpx.AsyncClient(timeout=30) as client:
            response = await client.request(method, f"{self.base}{path}", headers=self.headers, **kwargs)
            response.raise_for_status()
            return response.json()

    async def config(self, guild_id: int):
        return await self.request("GET", f"/guilds/{guild_id}/configuration")

    @staticmethod
    def embed(war: dict) -> discord.Embed:
        opponent = war.get("opponent") or "Not specified"
        embed = discord.Embed(title=f"⚔ {war['title']}", description=war.get("description") or "", colour=discord.Colour.dark_red())
        embed.add_field(name="Opponent", value=opponent, inline=False)
        assignments = war.get("assignments") or {}
        for wave in war.get("waves") or []:
            start = int(datetime.fromisoformat(str(wave["starts_at"]).replace("Z", "+00:00")).timestamp())
            members = [f"<@{user_id}>" for user_id, wave_id in assignments.items() if wave_id == wave["id"]]
            capacity = f"/{wave['capacity']}" if wave.get("capacity") else ""
            targets = wave.get("targets") or "Targets not assigned"
            roster = ", ".join(members[:20]) or "No participants"
            embed.add_field(
                name=f"{wave['name']} · {len(members)}{capacity}",
                value=f"<t:{start}:F> (<t:{start}:R>)\n**Targets:** {targets}\n**Squad:** {roster}",
                inline=False,
            )
        embed.set_footer(text="Choose one wave below. Selecting another wave moves your assignment.")
        return embed

    async def publish(self, guild: discord.Guild, war_id: str):
        config = await self.config(guild.id)
        war = next((value for value in config.get("wars", []) if value["id"] == war_id), None)
        if not config.get("enabled") or not war:
            raise RuntimeError("War plan unavailable")
        channel = guild.get_channel(int(war["channel_id"]))
        if not isinstance(channel, (discord.TextChannel, discord.Thread)):
            raise RuntimeError("War channel not found")
        old_message_id = war.get("message_id")
        if old_message_id:
            try:
                message = await channel.fetch_message(int(old_message_id))
                await message.edit(embed=self.embed(war), view=WarPlanView(war))
            except (discord.NotFound, discord.Forbidden):
                message = await channel.send(embed=self.embed(war), view=WarPlanView(war))
        else:
            message = await channel.send(embed=self.embed(war), view=WarPlanView(war))
        await self.request("POST", "/panel", json={"guild_id": guild.id, "war_id": war_id, "channel_id": str(channel.id), "message_id": str(message.id)})
        return message

    async def handle(self, interaction: discord.Interaction) -> bool:
        custom_id = str((interaction.data or {}).get("custom_id") or "")
        if not custom_id.startswith("gc-war:"):
            return False
        _, war_id, action = custom_id.split(":", 2)
        wave_id = None if action == "leave" else str(((interaction.data or {}).get("values") or [""])[0])
        try:
            await self.request("POST", "/signup", json={"guild_id": interaction.guild_id, "war_id": war_id, "wave_id": wave_id or None, "discord_user_id": interaction.user.id})
        except httpx.HTTPStatusError as exc:
            text = "This wave is full." if exc.response.status_code == 409 else "War plan is unavailable."
            await interaction.response.send_message(text, ephemeral=True)
            return True
        config = await self.config(interaction.guild_id)
        war = next(value for value in config["wars"] if value["id"] == war_id)
        await interaction.response.edit_message(embed=self.embed(war), view=WarPlanView(war))
        await interaction.followup.send("Assignment removed." if wave_id is None else "Your war wave was updated.", ephemeral=True)
        return True
