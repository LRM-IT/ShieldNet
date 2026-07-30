from fastapi import APIRouter,Depends
from sqlalchemy import func,select
from sqlalchemy.ext.asyncio import AsyncSession
from app.api.dependencies.auth import get_current_user
from app.api.dependencies.guild_access import require_guild_management
from app.db.session import get_db_session
from app.models.core import User
from app.models.discord import Guild
from app.models.guild_roles import DiscordGuildRole
from app.models.members import DiscordMember
from app.models.explorer import GuildChannel,GuildWebhook,GuildEmoji,GuildInvite
router=APIRouter(tags=["Discord Explorer"])
@router.get("/discord/guilds/{guild_id}/explorer")
async def explorer(guild_id:int,current_user:User=Depends(get_current_user),session:AsyncSession=Depends(get_db_session)):
 await require_guild_management(session,current_user,guild_id)
 guild=(await session.execute(select(Guild).where(Guild.guild_id==guild_id))).scalar_one()
 async def rows(model,order): return list((await session.execute(select(model).where(model.guild_id==guild_id).order_by(order))).scalars().all())
 roles=await rows(DiscordGuildRole,DiscordGuildRole.position.desc()); channels=await rows(GuildChannel,GuildChannel.position.asc()); webhooks=await rows(GuildWebhook,GuildWebhook.name.asc()); emojis=await rows(GuildEmoji,GuildEmoji.name.asc()); invites=await rows(GuildInvite,GuildInvite.code.asc())
 members=(await session.execute(select(func.count()).select_from(DiscordMember).where(DiscordMember.guild_id==guild_id,DiscordMember.is_active.is_(True)))).scalar_one()
 return {"guild":{"guild_id":guild.guild_id,"name":guild.name,"icon_url":guild.icon_url,"member_count":guild.member_count,"bot_status":guild.bot_status.value,"last_sync_at":guild.last_sync_at},"counts":{"members":members,"roles":len(roles),"channels":len(channels),"webhooks":len(webhooks),"emojis":len(emojis),"invites":len(invites)},"roles":[{"id":r.discord_role_id,"name":r.name,"position":r.position,"color":r.color,"permissions":r.permissions,"managed":r.managed,"assignable":r.assignable} for r in roles],"channels":[{"id":x.discord_channel_id,"parent_id":x.parent_id,"name":x.name,"type":x.channel_type,"position":x.position,"nsfw":x.nsfw,"topic":x.topic} for x in channels],"webhooks":[{"id":x.discord_webhook_id,"channel_id":x.channel_id,"name":x.name,"type":x.webhook_type,"owner_id":x.owner_id} for x in webhooks],"emojis":[{"id":x.discord_emoji_id,"name":x.name,"animated":x.animated,"managed":x.managed,"available":x.available} for x in emojis],"invites":[{"code":x.code,"channel_id":x.channel_id,"inviter_id":x.inviter_id,"uses":x.uses,"max_uses":x.max_uses,"temporary":x.temporary,"expires_at":x.expires_at} for x in invites]}
