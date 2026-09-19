from __future__ import annotations
from datetime import UTC,datetime
import httpx
import discord
from bot.config import settings
class ActivityRanking:
 def __init__(self,bot):self.bot=bot;self.base=settings.backend_url.rstrip('/')+'/api/v1/internal/plugin-activity-ranking';self.headers={'X-ShieldNet-Service-Token':settings.internal_service_token};self.cooldowns={};self.voice={}
 async def request(self,method,path,**kwargs):
  async with httpx.AsyncClient(timeout=20)as client:r=await client.request(method,f'{self.base}{path}',headers=self.headers,**kwargs);r.raise_for_status();return r.json()
 async def message(self,message):
  cfg=await self.request('GET',f'/guilds/{message.guild.id}/configuration')
  if not cfg.get('enabled'):return
  key=(message.guild.id,message.author.id);now=datetime.now(UTC).timestamp()
  if now-self.cooldowns.get(key,0)<cfg.get('message_cooldown_seconds',60):return
  self.cooldowns[key]=now;result=await self.request('POST','/activity',json={'guild_id':message.guild.id,'discord_user_id':message.author.id,'kind':'message','channel_id':str(message.channel.id),'role_ids':[str(r.id)for r in message.author.roles]});await self.apply_rewards(message.author,result,message)
 async def voice_state(self,member,before,after):
  key=(member.guild.id,member.id);now=datetime.now(UTC)
  if before.channel is None and after.channel is not None:self.voice[key]=(now,str(after.channel.id));return
  if before.channel is not None and(after.channel is None or before.channel.id!=after.channel.id):
   started=self.voice.pop(key,None)
   if started:
    minutes=max(0,(now-started[0]).total_seconds()/60);result=await self.request('POST','/activity',json={'guild_id':member.guild.id,'discord_user_id':member.id,'kind':'voice','amount':minutes,'channel_id':started[1],'role_ids':[str(r.id)for r in member.roles]});await self.apply_rewards(member,result)
   if after.channel is not None:self.voice[key]=(now,str(after.channel.id))
 async def leaderboard(self,guild_id,limit=10):return await self.request('GET',f'/guilds/{guild_id}/leaderboard?limit={limit}')
 async def apply_rewards(self,member,result,source_message=None):
  if not result.get('recorded'):return
  current={str(role.id)for role in member.roles};roles=[member.guild.get_role(int(role_id))for role_id in result.get('reward_role_ids',[])if str(role_id)not in current];roles=[role for role in roles if role is not None]
  if roles:
   try:await member.add_roles(*roles,reason=f"ShieldNet level {result.get('score',{}).get('level',1)} reward")
   except Exception:pass
  if result.get('leveled_up')and result.get('announce_level_up'):
   score=result.get('score',{});level=score.get('level',1);text=str(result.get('announcement_message')or'🎉 {member} reached level {level}!').replace('{member}',member.mention).replace('{level}',str(level)).replace('{xp}',str(score.get('points',0)))
   embed=discord.Embed(title=f'🏆 Level {level}',description=text,colour=discord.Colour.purple());embed.set_author(name=member.display_name,icon_url=member.display_avatar.url);embed.add_field(name='XP',value=f"{score.get('points',0):g}");embed.add_field(name='Reward roles',value=', '.join(role.mention for role in roles)or'—')
   if result.get('announce_in_reply')and source_message is not None:
    try:await source_message.reply(embed=embed,mention_author=False)
    except Exception:pass
   if result.get('announce_in_dm'):
    try:await member.send(embed=embed)
    except Exception:pass
   if result.get('announce_in_channel')and result.get('announcement_channel_id'):
    channel=member.guild.get_channel(int(result['announcement_channel_id']))
    if channel and hasattr(channel,'send'):
     try:await channel.send(embed=embed)
     except Exception:pass
