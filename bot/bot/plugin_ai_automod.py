from __future__ import annotations
import logging
from datetime import UTC,datetime,timedelta
import discord,httpx
from bot.config import settings
logger=logging.getLogger(__name__)

class AIAutoMod:
    def __init__(self,bot):self.bot=bot;self.url=settings.backend_url.rstrip("/")+"/api/v1/internal/plugin-ai-automod/analyze";self.headers={"X-ShieldNet-Service-Token":settings.internal_service_token}
    async def process(self,message:discord.Message)->None:
        if message.guild is None or message.author.bot or message.webhook_id or not message.content.strip():return
        payload={"guild_id":message.guild.id,"discord_user_id":message.author.id,"channel_id":message.channel.id,"message_id":message.id,"content":message.content,"role_ids":[r.id for r in getattr(message.author,"roles",[])],"message_url":message.jump_url}
        async with httpx.AsyncClient(timeout=90) as client:
            response=await client.post(self.url,headers=self.headers,json=payload)
        if response.status_code==409:return
        response.raise_for_status();result=response.json()
        if not result.get("flagged"):return
        actions=result.get("actions") or {};reason=str(result.get("reason") or "Policy violation")
        if actions.get("delete_message"):
            try:await message.delete()
            except discord.HTTPException:logger.warning("AI AutoMod could not delete message=%s",message.id)
        minutes=int(actions.get("timeout_minutes") or 0)
        if minutes and isinstance(message.author,discord.Member):
            try:await message.author.timeout(datetime.now(UTC)+timedelta(minutes=minutes),reason=f"GuildConsole AI AutoMod: {reason}"[:512])
            except discord.HTTPException:logger.warning("AI AutoMod could not timeout member=%s",message.author.id)
        if actions.get("warn_member"):
            warning=str(actions.get("warning_text") or "Your message was moderated: {reason}").replace("{reason}",reason)
            try:await message.author.send(warning)
            except discord.HTTPException:
                try:await message.channel.send(f"{message.author.mention} {warning}",delete_after=12)
                except discord.HTTPException:pass
        log_id=actions.get("log_channel_id")
        if log_id:
            channel=message.guild.get_channel(int(log_id))
            if isinstance(channel,(discord.TextChannel,discord.Thread)):
                embed=discord.Embed(title="AI AutoMod",description=reason,colour=discord.Colour.orange(),timestamp=datetime.now(UTC));embed.add_field(name="Member",value=f"{message.author} (`{message.author.id}`)");embed.add_field(name="Category",value=str(result.get("category") or "other"));embed.add_field(name="Confidence",value=f"{float(result.get('confidence') or 0):.0%}");embed.add_field(name="Message",value=message.content[:1000] or "—",inline=False)
                if result.get("case_id"):embed.set_footer(text=f"Case {result['case_id']}")
                try:await channel.send(embed=embed)
                except discord.HTTPException:pass
