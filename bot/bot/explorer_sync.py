import discord,httpx
from bot.config import settings
class ExplorerSyncClient:
 async def synchronize(self,guild:discord.Guild)->None:
  webhooks=[]; invites=[]
  try:
   for x in await guild.webhooks(): webhooks.append({"discord_webhook_id":x.id,"channel_id":x.channel_id,"name":x.name,"webhook_type":str(x.type).split('.')[-1],"owner_id":x.user.id if x.user else None})
  except discord.Forbidden: pass
  try:
   for x in await guild.invites(): invites.append({"code":x.code,"channel_id":x.channel.id if x.channel else None,"inviter_id":x.inviter.id if x.inviter else None,"uses":x.uses or 0,"max_uses":x.max_uses or 0,"temporary":x.temporary,"expires_at":x.expires_at.isoformat() if x.expires_at else None})
  except discord.Forbidden: pass
  permission_overwrites=[]
  for channel in guild.channels:
   for target, overwrite in channel.overwrites.items():
    allow, deny = overwrite.pair()
    permission_overwrites.append({"discord_channel_id":channel.id,"target_id":target.id,"target_type":"role" if isinstance(target,discord.Role) else "member","allow_permissions":allow.value,"deny_permissions":deny.value})
  payload={"channels":[{"discord_channel_id":x.id,"parent_id":x.parent_id if isinstance(x,discord.Thread) else x.category_id,"name":x.name,"channel_type":str(x.type).split('.')[-1],"position":x.position,"nsfw":getattr(x,"nsfw",False),"topic":getattr(x,"topic",None),"permissions_synced":getattr(x,"permissions_synced",False)} for x in [*guild.channels,*guild.threads]],"webhooks":webhooks,"emojis":[{"discord_emoji_id":x.id,"name":x.name,"animated":x.animated,"managed":x.managed,"available":x.available} for x in guild.emojis],"invites":invites,"permission_overwrites":permission_overwrites}
  async with httpx.AsyncClient(timeout=30) as c:
   r=await c.post(f"{settings.backend_url.rstrip('/')}/api/v1/internal/discord/guilds/{guild.id}/explorer/sync",headers={"X-ShieldNet-Service-Token":settings.internal_service_token},json=payload); r.raise_for_status()
