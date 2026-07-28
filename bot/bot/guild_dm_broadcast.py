from __future__ import annotations
import asyncio
import logging
from typing import Any
import discord
import httpx
from bot.config import settings

logger=logging.getLogger(__name__)

class GuildDMBroadcastWorker:
    def __init__(self,bot:discord.Client)->None:
        self.bot=bot
        self.base=settings.backend_url.rstrip("/")
        self.headers={"X-ShieldNet-Service-Token":settings.internal_service_token,
                      "Content-Type":"application/json"}

    async def run_once(self)->None:
        async with httpx.AsyncClient(timeout=30) as client:
            r=await client.get(f"{self.base}/api/v1/internal/plugin-guild-dm-broadcast/campaigns/pending",headers=self.headers)
            r.raise_for_status(); item=r.json().get("item")
        if not item:return
        cid=str(item["id"]); sent=failed=skipped=0; details:list[dict[str,Any]]=[]
        try:
            guild=self.bot.get_guild(int(item["guild_id"]))
            if guild is None:raise RuntimeError("Discord guild is unavailable")
            if not guild.chunked:await guild.chunk(cache=True)
            roles={int(x) for x in(item.get("role_ids") or [])}
            member_ids={int(x) for x in(item.get("member_ids") or [])}
            delay=max(int(item.get("delay_ms",1200)),750)/1000
            members=[]
            for member in guild.members:
                if member_ids and member.id not in member_ids:
                    skipped+=1;continue
                if item.get("exclude_bots",True) and member.bot:
                    skipped+=1;continue
                if roles and not roles.intersection(r.id for r in member.roles):
                    skipped+=1;continue
                members.append(member)
            for member in members:
                if await self._cancelled(cid):
                    await self._report(cid,"cancelled",sent,failed,skipped,None,details);return
                content=str(item["message"])
                content=content.replace("{username}",member.name)
                content=content.replace("{display_name}",member.display_name)
                content=content.replace("{guild}",guild.name)
                try:
                    await member.send(content);sent+=1
                    details.append({"discord_user_id":member.id,"status":"sent"})
                except discord.Forbidden as exc:
                    failed+=1;details.append({"discord_user_id":member.id,"status":"forbidden","error":str(exc)})
                except discord.HTTPException as exc:
                    failed+=1;details.append({"discord_user_id":member.id,"status":"http_error","error":str(exc)})
                except Exception as exc:
                    failed+=1;details.append({"discord_user_id":member.id,"status":"failed","error":str(exc)})
                await asyncio.sleep(delay)
            await self._report(cid,"completed",sent,failed,skipped,None,details)
        except Exception as exc:
            logger.exception("Guild DM campaign failed id=%s",cid)
            await self._report(cid,"failed",sent,failed,skipped,str(exc),details)

    async def _cancelled(self,cid:str)->bool:
        async with httpx.AsyncClient(timeout=15) as client:
            r=await client.get(f"{self.base}/api/v1/internal/plugin-guild-dm-broadcast/campaigns/{cid}/state",headers=self.headers)
            r.raise_for_status();return r.json().get("status")=="cancelled"

    async def _report(self,cid:str,status:str,sent:int,failed:int,skipped:int,error:str|None,details:list[dict[str,Any]])->None:
        async with httpx.AsyncClient(timeout=60) as client:
            r=await client.post(f"{self.base}/api/v1/internal/plugin-guild-dm-broadcast/campaigns/{cid}/result",
                headers=self.headers,json={"status":status,"sent":sent,"failed":failed,
                "skipped":skipped,"error":error,"details":details})
            r.raise_for_status()
