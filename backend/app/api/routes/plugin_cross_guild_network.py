from __future__ import annotations
import secrets
from uuid import uuid4
from fastapi import APIRouter,Depends,HTTPException
from pydantic import BaseModel,Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.api.dependencies.auth import get_current_user
from app.api.dependencies.guild_access import require_guild_module
from app.db.session import get_db_session
from app.models.core import User
from app.models.discord import Guild
from app.models.plugins import GuildPluginInstallation
from app.models.role_channel_management import DiscordStructureChange
router=APIRouter(tags=["Cross-Guild Network plugin"])
class CreateInput(BaseModel):name:str=Field(min_length=2,max_length=100);channel_id:str|None=None
class JoinInput(BaseModel):invite_code:str=Field(min_length=4,max_length=64);channel_id:str
class SettingsInput(BaseModel):channel_id:str|None=None
class AnnouncementInput(BaseModel):title:str=Field(min_length=1,max_length=200);message:str=Field(min_length=1,max_length=3000)
async def installation(session,guild_id,lock=False):
 q=select(GuildPluginInstallation).where(GuildPluginInstallation.guild_id==guild_id,GuildPluginInstallation.plugin_key=="cross_guild_network");return await session.scalar(q.with_for_update()if lock else q)
def network(item):return(item.configuration or{}).get("network")if item else None
async def response(session,guild_id):
 item=await installation(session,guild_id);net=network(item);members=[]
 if net:
  ids=[int(x)for x in net.get("member_guild_ids",[])];guilds=(await session.execute(select(Guild).where(Guild.guild_id.in_(ids or[0])))).scalars().all();names={str(x.guild_id):x.name for x in guilds};members=[{"guild_id":x,"name":names.get(str(x),f"Server {x}"),"owner":int(x)==int(net["owner_guild_id"])}for x in ids]
 return{"installed":item is not None,"enabled":bool(item and item.enabled),"channel_id":(item.configuration or{}).get("channel_id")if item else None,"network":net,"members":members}
async def network_items(session,network_id,lock=False):
 q=select(GuildPluginInstallation).where(GuildPluginInstallation.plugin_key=="cross_guild_network");q=q.with_for_update()if lock else q;items=(await session.execute(q)).scalars().all();return[item for item in items if(network(item)or{}).get("id")==network_id]
@router.get("/discord/guilds/{guild_id}/plugins/cross-guild-network/settings")
async def get_settings(guild_id:int,user:User=Depends(get_current_user),session:AsyncSession=Depends(get_db_session)):
 await require_guild_module(session,user,guild_id,"plugins");return await response(session,guild_id)
@router.post("/discord/guilds/{guild_id}/plugins/cross-guild-network/create")
async def create(guild_id:int,payload:CreateInput,user:User=Depends(get_current_user),session:AsyncSession=Depends(get_db_session)):
 await require_guild_module(session,user,guild_id,"plugins");item=await installation(session,guild_id,True)
 if not item:raise HTTPException(409,"Install Cross-Guild Network first")
 if network(item):raise HTTPException(409,"This server already belongs to a network")
 net={"id":str(uuid4()),"name":payload.name.strip(),"owner_guild_id":str(guild_id),"invite_code":secrets.token_urlsafe(8),"member_guild_ids":[str(guild_id)]};item.configuration={**(item.configuration or{}),"channel_id":payload.channel_id,"network":net};await session.commit();return await response(session,guild_id)
@router.post("/discord/guilds/{guild_id}/plugins/cross-guild-network/join")
async def join(guild_id:int,payload:JoinInput,user:User=Depends(get_current_user),session:AsyncSession=Depends(get_db_session)):
 await require_guild_module(session,user,guild_id,"plugins");item=await installation(session,guild_id,True)
 if not item:raise HTTPException(409,"Install Cross-Guild Network first")
 if network(item):raise HTTPException(409,"This server already belongs to a network")
 all_items=(await session.execute(select(GuildPluginInstallation).where(GuildPluginInstallation.plugin_key=="cross_guild_network").with_for_update())).scalars().all();source=next((x for x in all_items if secrets.compare_digest(str((network(x)or{}).get("invite_code")or""),payload.invite_code.strip())),None)
 if not source:raise HTTPException(404,"Invite code not found")
 net=dict(network(source));members=list(net.get("member_guild_ids",[]));members.append(str(guild_id));net["member_guild_ids"]=list(dict.fromkeys(members))
 for peer in[x for x in all_items if(network(x)or{}).get("id")==net["id"]]:peer.configuration={**(peer.configuration or{}),"network":net}
 item.configuration={**(item.configuration or{}),"channel_id":payload.channel_id,"network":net};await session.commit();return await response(session,guild_id)
@router.put("/discord/guilds/{guild_id}/plugins/cross-guild-network/settings")
async def save(guild_id:int,payload:SettingsInput,user:User=Depends(get_current_user),session:AsyncSession=Depends(get_db_session)):
 await require_guild_module(session,user,guild_id,"plugins");item=await installation(session,guild_id,True)
 if not item:raise HTTPException(409,"Install Cross-Guild Network first")
 item.configuration={**(item.configuration or{}),"channel_id":payload.channel_id};await session.commit();return await response(session,guild_id)
@router.post("/discord/guilds/{guild_id}/plugins/cross-guild-network/rotate-code")
async def rotate(guild_id:int,user:User=Depends(get_current_user),session:AsyncSession=Depends(get_db_session)):
 await require_guild_module(session,user,guild_id,"plugins");item=await installation(session,guild_id);net=network(item)
 if not net or int(net["owner_guild_id"])!=guild_id:raise HTTPException(403,"Only the network owner can rotate the code")
 net={**net,"invite_code":secrets.token_urlsafe(8)}
 for peer in await network_items(session,net["id"],True):peer.configuration={**(peer.configuration or{}),"network":net}
 await session.commit();return await response(session,guild_id)
@router.post("/discord/guilds/{guild_id}/plugins/cross-guild-network/announce")
async def announce(guild_id:int,payload:AnnouncementInput,user:User=Depends(get_current_user),session:AsyncSession=Depends(get_db_session)):
 await require_guild_module(session,user,guild_id,"plugins");item=await installation(session,guild_id);net=network(item)
 if not net or int(net["owner_guild_id"])!=guild_id:raise HTTPException(403,"Only the network owner can announce")
 count=0
 for peer in await network_items(session,net["id"]):
  channel=(peer.configuration or{}).get("channel_id")
  if peer.enabled and channel:
   session.add(DiscordStructureChange(guild_id=peer.guild_id,object_type="network_announcement",operation="publish",payload={"channel_id":channel,"network_name":net["name"],"title":payload.title,"message":payload.message},preview={"safe_to_apply":True},status="pending",requested_by=user.id));count+=1
 await session.commit();return{"queued":count}
@router.post("/discord/guilds/{guild_id}/plugins/cross-guild-network/leave")
async def leave(guild_id:int,user:User=Depends(get_current_user),session:AsyncSession=Depends(get_db_session)):
 await require_guild_module(session,user,guild_id,"plugins");item=await installation(session,guild_id,True);net=network(item)
 if not net:raise HTTPException(409,"Server is not in a network")
 peers=await network_items(session,net["id"],True)
 if int(net["owner_guild_id"])==guild_id:
  for peer in peers:peer.configuration={**(peer.configuration or{}),"network":None}
 else:
  updated={**net,"member_guild_ids":[x for x in net.get("member_guild_ids",[])if int(x)!=guild_id]}
  for peer in peers:peer.configuration={**(peer.configuration or{}),"network":None if peer.guild_id==guild_id else updated}
 await session.commit();return await response(session,guild_id)
