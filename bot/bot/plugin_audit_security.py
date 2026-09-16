from __future__ import annotations
import discord,httpx
from bot.config import settings
class AuditSecurity:
 def __init__(self,bot):self.bot=bot;self.base=settings.backend_url.rstrip('/')+'/api/v1/internal/plugin-audit-security';self.headers={'X-ShieldNet-Service-Token':settings.internal_service_token}
 async def record(self,guild,event_type,title,description='',target_id=None,severity='info',metadata=None):
  async with httpx.AsyncClient(timeout=20)as client:r=await client.post(f'{self.base}/event',headers=self.headers,json={'guild_id':guild.id,'event_type':event_type,'target_id':str(target_id)if target_id else None,'title':title,'description':description,'severity':severity,'metadata':metadata or{}});r.raise_for_status();data=r.json()
  if not data.get('recorded')or not data.get('log_channel_id'):return
  channel=guild.get_channel(int(data['log_channel_id']))
  if not isinstance(channel,(discord.TextChannel,discord.Thread)):return
  colors={'info':discord.Colour.blurple(),'low':discord.Colour.green(),'medium':discord.Colour.orange(),'high':discord.Colour.red(),'critical':discord.Colour.dark_red()};embed=discord.Embed(title=title,description=description,colour=colors[severity]);embed.set_footer(text=event_type.replace('_',' ').title())
  mention=f"<@&{data['mention_role_id']}>"if data.get('mention_role_id')and severity in{'high','critical'}else None;await channel.send(content=mention,embed=embed,allowed_mentions=discord.AllowedMentions(roles=True))
