from __future__ import annotations
from datetime import UTC,datetime
import httpx
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
  self.cooldowns[key]=now;result=await self.request('POST','/activity',json={'guild_id':message.guild.id,'discord_user_id':message.author.id,'kind':'message','channel_id':str(message.channel.id),'role_ids':[str(r.id)for r in message.author.roles]});await self.apply_rewards(message.author,result)
 async def voice_state(self,member,before,after):
  key=(member.guild.id,member.id);now=datetime.now(UTC)
  if before.channel is None and after.channel is not None:self.voice[key]=(now,str(after.channel.id));return
  if before.channel is not None and(after.channel is None or before.channel.id!=after.channel.id):
   started=self.voice.pop(key,None)
   if started:
    minutes=max(0,(now-started[0]).total_seconds()/60);result=await self.request('POST','/activity',json={'guild_id':member.guild.id,'discord_user_id':member.id,'kind':'voice','amount':minutes,'channel_id':started[1],'role_ids':[str(r.id)for r in member.roles]});await self.apply_rewards(member,result)
   if after.channel is not None:self.voice[key]=(now,str(after.channel.id))
 async def leaderboard(self,guild_id,limit=10):return await self.request('GET',f'/guilds/{guild_id}/leaderboard?limit={limit}')
 async def apply_rewards(self,member,result):
  if not result.get('recorded'):return
  current={str(role.id)for role in member.roles};roles=[member.guild.get_role(int(role_id))for role_id in result.get('reward_role_ids',[])if str(role_id)not in current];roles=[role for role in roles if role is not None]
  if roles:
   try:await member.add_roles(*roles,reason=f"ShieldNet level {result.get('score',{}).get('level',1)} reward")
   except Exception:return
