from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from typing import Literal
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies.auth import get_current_user
from app.api.dependencies.guild_access import require_guild_management
from app.db.session import get_db_session
from app.models.core import User
from app.models.discord import Guild
from app.models.guild_languages import GuildLanguage
from app.models.role_channel_management import DiscordStructureChange

router = APIRouter(tags=["Core server setup wizard"])

class WizardApply(BaseModel):
    name: str = Field(min_length=2, max_length=100)
    icon_data: str | None = Field(default=None, max_length=1_500_000)
    description: str = Field(default="", max_length=300)
    game: str = Field(default="", max_length=100)
    system_channel_name: str = Field(min_length=1, max_length=100)
    template_key: Literal["minimal", "community", "gaming", "clan", "support", "creator", "education", "business", "global_alliance", "esports", "tournament", "roleplay", "music", "technology", "marketplace"] = "community"

STRUCTURES = {
    "minimal": [("START", [("text","welcome",True),("text","rules",False),("text","general",False)])],
    "community": [("INFORMATION", [("text","welcome",True),("text","rules",False),("text","announcements",False)]),("COMMUNITY",[("text","general",False),("text","introductions",False),("text","media",False)]),("VOICE",[("voice","Lobby",False),("voice","General",False)])],
    "gaming": [("START HERE", [("text","welcome",True),("text","rules",False),("text","choose-roles",False)]),("GAME",[("text","general",False),("text","looking-for-group",False),("text","clips-and-media",False)]),("VOICE",[("voice","Lobby",False),("voice","Squad 1",False),("voice","Squad 2",False)])],
    "clan": [("HEADQUARTERS", [("text","welcome",True),("text","announcements",False),("text","rules",False)]),("OPERATIONS",[("text","strategy",False),("text","events",False),("text","recruitment",False)]),("VOICE",[("voice","Command",False),("voice","Squad",False)])],
    "support": [("INFORMATION", [("text","welcome",True),("text","announcements",False),("text","faq",False)]),("SUPPORT",[("text","help-desk",False),("text","resolved-cases",False)]),("COMMUNITY",[("text","general",False)]),("VOICE",[("voice","Support room",False)])],
    "creator": [("WELCOME", [("text","welcome",True),("text","rules",False),("text","announcements",False)]),("CONTENT",[("text","new-content",False),("text","clips-and-media",False),("text","ideas-and-feedback",False)]),("COMMUNITY",[("text","general",False),("text","off-topic",False)]),("LIVE ROOMS",[("voice","Live lobby",False),("voice","Community stage",False)])],
    "education": [("START HERE", [("text","welcome",True),("text","rules",False),("text","announcements",False)]),("LEARNING",[("text","lessons",False),("text","homework",False),("text","resources",False),("text","questions",False)]),("STUDY ROOMS",[("voice","Study room 1",False),("voice","Study room 2",False)])],
    "business": [("COMPANY", [("text","welcome",True),("text","announcements",False),("text","policies",False)]),("WORKSPACE",[("text","general",False),("text","projects",False),("text","reports",False),("text","ideas",False)]),("MEETINGS",[("voice","Meeting room",False),("voice","Private meeting",False)])],
    "global_alliance": [("START", [("text","welcome",True),("text","rules",False),("text","verify",False),("text","choose-language",False),("text","announcements",False)]),("VERIFICATION",[("text","how-to-verify",False),("text","apply-r5-r4",False),("text","verification-status",False),("text","approved",False),("text","rejected",False)]),("R5 LEADERS",[("text","us-r5-leader-chat-english",False),("text","kr-r5-leader-chat-korean",False),("text","jp-r5-leader-chat-japanese",False),("text","cn-r5-leader-chat-chinese",False),("text","id-r5-leader-chat-indonesian",False),("text","fr-r5-leader-chat-french",False),("text","sa-r5-leader-chat-arabic",False),("text","ru-r5-leader-chat-russian",False),("text","r5-leader-voting",False)]),("R5 R4",[("text","us-r4-r5-main-chat-english",False),("text","kr-r4-r5-chat-korean",False),("text","jp-r4-r5-chat-japanese",False),("text","de-r4-r5-chat-german",False),("text","map-rotation",False),("text","our-opponents",False),("text","voting",False),("voice","r5-r4-voice",False)]),("SVS COMMAND CENTER",[("text","svs-defense",False),("text","svs-offense",False),("text","intel-reports",False),("text","battle-plans",False),("text","command-chat",False),("text","event-schedule",False)]),("ALLIANCE BATTLES",[("text","alliance-opponents",False),("text","desert-opponents",False),("text","enemy-coordinates",False)]),("GLOBAL",[("text","us-english-chat",False),("text","eu-russian-chat",False),("text","kr-korean-chat",False),("text","jp-japanese-chat",False),("text","id-indonesian-chat",False),("text","cn-chinese-chat",False),("text","de-german-chat",False),("text","fr-french-chat",False),("text","es-spanish-chat",False),("text","sa-chat-arabic",False)]),("GAMEPLAY",[("text","recommendations-from-tops",False),("text","ascii-art",False),("text","news-and-events",False),("text","update-note",False)]),("SUPPORT CENTER",[("text","report-issue",False),("text","resolved",False),("text","suggestions",False)])],
    "esports": [("TEAM HQ",[("text","welcome",True),("text","team-news",False),("text","rules",False)]),("COMPETITIVE",[("text","match-schedule",False),("text","strategies",False),("text","vod-review",False),("text","scrim-results",False)]),("RECRUITMENT",[("text","applications",False),("text","tryout-results",False)]),("TEAM VOICE",[("voice","Practice",False),("voice","Match room",False),("voice","Coaches",False)])],
    "tournament": [("TOURNAMENT INFO",[("text","welcome",True),("text","rules",False),("text","announcements",False),("text","schedule",False)]),("PARTICIPANTS",[("text","registration",False),("text","team-captains",False),("text","find-a-team",False)]),("MATCH CENTER",[("text","results",False),("text","disputes",False),("text","highlights",False)]),("MATCH ROOMS",[("voice","Match 1",False),("voice","Match 2",False),("voice","Broadcast",False)])],
    "roleplay": [("WELCOME",[("text","welcome",True),("text","world-rules",False),("text","announcements",False)]),("CHARACTERS",[("text","character-creation",False),("text","character-sheets",False),("text","lore",False)]),("ROLEPLAY",[("text","town-square",False),("text","tavern",False),("text","quests",False)]),("VOICE SCENES",[("voice","Scene 1",False),("voice","Scene 2",False)])],
    "music": [("INFO",[("text","welcome",True),("text","rules",False),("text","releases",False)]),("MUSIC",[("text","share-your-music",False),("text","feedback",False),("text","collaborations",False),("text","playlists",False)]),("STUDIO",[("voice","Listening party",False),("voice","Jam room",False),("voice","Recording room",False)])],
    "technology": [("PROJECT",[("text","welcome",True),("text","announcements",False),("text","roadmap",False)]),("DEVELOPMENT",[("text","general-dev",False),("text","frontend",False),("text","backend",False),("text","devops",False)]),("OPERATIONS",[("text","bug-reports",False),("text","incidents",False),("text","releases",False)]),("MEETINGS",[("voice","Daily standup",False),("voice","Pair programming",False)])],
    "marketplace": [("MARKET INFO",[("text","welcome",True),("text","rules",False),("text","verified-sellers",False)]),("LISTINGS",[("text","offers",False),("text","requests",False),("text","auctions",False)]),("TRUST & SUPPORT",[("text","reviews",False),("text","disputes",False),("text","report-seller",False)]),("DEAL ROOMS",[("voice","Deal room 1",False),("voice","Deal room 2",False)])],
}

LANGUAGE_CHANNEL_CODES = {
    "us-r5-leader-chat-english":"en", "kr-r5-leader-chat-korean":"ko", "jp-r5-leader-chat-japanese":"ja", "cn-r5-leader-chat-chinese":"zh", "id-r5-leader-chat-indonesian":"id", "fr-r5-leader-chat-french":"fr", "sa-r5-leader-chat-arabic":"ar", "ru-r5-leader-chat-russian":"ru",
    "us-r4-r5-main-chat-english":"en", "kr-r4-r5-chat-korean":"ko", "jp-r4-r5-chat-japanese":"ja", "de-r4-r5-chat-german":"de",
    "us-english-chat":"en", "eu-russian-chat":"ru", "kr-korean-chat":"ko", "jp-japanese-chat":"ja", "id-indonesian-chat":"id", "cn-chinese-chat":"zh", "de-german-chat":"de", "fr-french-chat":"fr", "es-spanish-chat":"es", "sa-chat-arabic":"ar",
}

def alliance_language_channel(code: str, category: str) -> str:
    prefix={"en":"us-english","uk":"ua-ukrainian","ru":"eu-russian","de":"de-german","fr":"fr-french","es":"es-spanish","it":"it-italian","pl":"pl-polish","pt":"pt-portuguese","ar":"sa-arabic","ko":"kr-korean","ja":"jp-japanese","zh":"cn-chinese","id":"id-indonesian","vi":"vn-vietnamese","lv":"lv-latvian","lt":"lt-lithuanian"}.get(code,f"{code}-{code}")
    if category=="R5 LEADERS": return f"{prefix}-r5-leader-chat"
    if category=="R5 R4": return f"{prefix}-r4-r5-chat"
    return f"{prefix}-chat"

async def enabled_language_codes(db: AsyncSession, guild_id: int) -> list[str]:
    return list((await db.execute(select(GuildLanguage.language_code).where(
        GuildLanguage.guild_id == guild_id, GuildLanguage.enabled.is_(True)
    ).order_by(GuildLanguage.sort_order))).scalars())

def change_payload(item: DiscordStructureChange | None):
    if not item: return None
    return {"id":str(item.id),"status":item.status,"message":item.result_message,"result":(item.payload or {}).get("_result",{})}

@router.get("/discord/guilds/{guild_id}/setup-wizard")
async def state(guild_id:int,user:User=Depends(get_current_user),db:AsyncSession=Depends(get_db_session)):
    await require_guild_management(db,user,guild_id)
    guild=await db.get(Guild,guild_id)
    jobs=(await db.execute(select(DiscordStructureChange).where(
        DiscordStructureChange.guild_id==guild_id,
        DiscordStructureChange.preview["wizard_plugin"].as_boolean().is_(True),
    ).order_by(DiscordStructureChange.created_at.desc()).limit(200))).scalars().all()
    by_kind={}
    for job in jobs: by_kind.setdefault(job.object_type,job)
    profile=by_kind.get("guild_profile"); channel=by_kind.get("wizard_system_channel"); check=by_kind.get("permission_check")
    batch=[job for job in jobs if profile and job.created_at>=profile.created_at]
    completed=bool(profile and channel and batch and all(job.status=="completed" for job in batch))
    result=(channel.payload or {}).get("_result",{}) if channel else {}
    configuration={"game":(profile.payload or {}).get("game","") if profile else "","description":(profile.payload or {}).get("description","") if profile else "","system_channel_id":result.get("channel_id"),"system_channel_name":(channel.payload or {}).get("name") if channel else None}
    languages=await enabled_language_codes(db,guild_id)
    return {"completed":completed,"running":any(job.status in {"pending","processing"} for job in batch),"failed_jobs":[change_payload(job) for job in batch if job.status=="failed"],"guild":{"name":guild.name,"icon_url":guild.icon_url},"server_languages":languages,"permission_check":change_payload(check),"profile_job":change_payload(profile),"channel_job":change_payload(channel),"configuration":configuration}

@router.post("/discord/guilds/{guild_id}/setup-wizard/check")
async def check(guild_id:int,user:User=Depends(get_current_user),db:AsyncSession=Depends(get_db_session)):
    await require_guild_management(db,user,guild_id)
    languages=await enabled_language_codes(db,guild_id)
    if payload.template_key=="global_alliance" and not languages:
        raise HTTPException(422,{"code":"server_languages_required","message":"Configure server languages before applying the Global Game Alliance template.","settings_url":f"/guild/{guild_id}/languages"})
    job=DiscordStructureChange(guild_id=guild_id,object_type="permission_check",operation="check",payload={},preview={"safe_to_apply":True,"wizard_plugin":True},status="pending",requested_by=user.id)
    db.add(job);await db.commit();return {"job_id":str(job.id)}

@router.post("/discord/guilds/{guild_id}/setup-wizard/apply")
async def apply(guild_id:int,payload:WizardApply,user:User=Depends(get_current_user),db:AsyncSession=Depends(get_db_session)):
    await require_guild_management(db,user,guild_id)
    pending=await db.scalar(select(DiscordStructureChange).where(DiscordStructureChange.guild_id==guild_id,DiscordStructureChange.preview["wizard_plugin"].as_boolean().is_(True),DiscordStructureChange.status.in_(["pending","processing"])))
    if pending: raise HTTPException(409,"Wizard setup is already running")
    profile=DiscordStructureChange(guild_id=guild_id,object_type="guild_profile",operation="update",payload={"name":payload.name.strip(),"icon_data":payload.icon_data,"description":payload.description.strip(),"game":payload.game.strip()},preview={"safe_to_apply":True,"wizard_plugin":True},status="pending",requested_by=user.id)
    db.add(profile);await db.flush();queued=[profile];system_job=None
    for category_name, channels in STRUCTURES[payload.template_key]:
        if payload.template_key=="global_alliance":
            channels=[item for item in channels if item[1] not in LANGUAGE_CHANNEL_CODES]
            if category_name in {"R5 LEADERS","R5 R4","GLOBAL"}:
                channels=[*(('text',alliance_language_channel(code,category_name),False) for code in languages),*channels]
        category=DiscordStructureChange(guild_id=guild_id,object_type="category",operation="create",payload={"name":category_name},preview={"safe_to_apply":True,"wizard_plugin":True,"template":payload.template_key},status="pending",requested_by=user.id)
        db.add(category);await db.flush();queued.append(category)
        for channel_type,name,is_system in channels:
            actual_name=payload.system_channel_name.strip() if is_system else name
            item=DiscordStructureChange(guild_id=guild_id,object_type="wizard_system_channel" if is_system else "channel",operation="create",payload={"name":actual_name,"channel_type":channel_type,"topic":payload.description.strip() if is_system else None,"position":0 if is_system else None,"set_system_channel":is_system,"_parent_change_id":str(category.id)},preview={"safe_to_apply":True,"wizard_plugin":True,"template":payload.template_key},status="pending",requested_by=user.id)
            db.add(item);queued.append(item)
            if is_system: system_job=item
    await db.commit()
    return {"status":"queued","queued":len(queued),"profile_job_id":str(profile.id),"channel_job_id":str(system_job.id) if system_job else None}
