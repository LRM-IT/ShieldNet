from __future__ import annotations
import time
import discord, httpx
from bot.config import settings

class VerificationLevelsClient:
    def __init__(self, bot: discord.Client):
        self.bot=bot; self.base=settings.backend_url.rstrip("/")+"/api/v1/internal/verification-levels"
        self.headers={"X-ShieldNet-Service-Token":settings.internal_service_token}; self.cache={}

    async def levels(self,guild_id:int)->list[dict]:
        cached=self.cache.get(guild_id)
        if cached and cached[0]>time.monotonic(): return cached[1]
        async with httpx.AsyncClient(timeout=20) as client:
            response=await client.get(f"{self.base}/guilds/{guild_id}",headers=self.headers); response.raise_for_status(); rows=response.json()["levels"]
        self.cache[guild_id]=(time.monotonic()+30,rows); return rows

    async def process(self,message:discord.Message)->None:
        if message.guild is None or message.author.bot or message.webhook_id: return
        level=next((item for item in await self.levels(message.guild.id) if item.get("channel_id")==str(message.channel.id)),None)
        if level is None: return
        image=next((item for item in message.attachments if (item.content_type or "").startswith("image/") or item.filename.lower().endswith((".png",".jpg",".jpeg",".webp"))),None)
        if image is None:
            await message.reply("Upload an image of your game profile for this verification level.",mention_author=False); return
        async with message.channel.typing():
            async with httpx.AsyncClient(timeout=120) as client:
                response=await client.post(f"{self.base}/analyze",headers=self.headers,json={"guild_id":message.guild.id,"level_id":level["id"],"discord_user_id":message.author.id,"discord_message_id":message.id,"image_url":image.url})
        if response.is_error:
            await message.reply("The image could not be analyzed. Try again or contact an administrator.",mention_author=False); return
        result=response.json()
        if not result["matched"]:
            await message.reply(f"❌ Level **{result['level_name']}** was not verified. {result.get('reason') or ''}",mention_author=False); return
        member=message.author if isinstance(message.author,discord.Member) else message.guild.get_member(message.author.id)
        roles=[role for role_id in result.get("role_ids",[]) if (role:=message.guild.get_role(int(role_id))) and role < message.guild.me.top_role]
        if member and roles: await member.add_roles(*roles,reason=f"GuildConsole verification: {result['level_name']}")
        matches=", ".join(result.get("matched_criteria") or [])
        await message.reply(f"✅ Level **{result['level_name']}** verified."+(f" Matches: **{matches}**." if matches else "")+(f" Detected: `{result['detected_text']}`" if result.get("detected_text") else ""),mention_author=False)
