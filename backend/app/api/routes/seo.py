from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies.platform_access import require_superadmin
from app.db.session import get_db_session
from app.models.core import User
from app.services.settings import SettingsService

router=APIRouter(tags=["Public SEO"]);MODULE="public_seo"
DEFAULTS={"site_name":"GuildConsole","title":"GuildConsole — керування Discord-серверами","description":"GuildConsole — захищена панель керування Discord-серверами, автоматизацією, безпекою, модерацією та плагінами.","keywords":"Discord, керування Discord сервером, Discord бот, автоматизація Discord, модерація Discord, GuildConsole","canonical_url":"https://guildconsole.lrm-it.com/","og_title":"GuildConsole — контроль Discord-інфраструктури","og_description":"Керуйте Discord-серверами, безпекою, автоматизацією та плагінами з єдиної захищеної панелі.","og_image":"","robots":"index,follow","analytics_enabled":False,"google_analytics_id":"","google_tag_manager_id":"","meta_pixel_id":"","yandex_metrika_id":"","clarity_project_id":""}

class SeoUpdate(BaseModel):
    site_name:str=Field(max_length=100);title:str=Field(max_length=200);description:str=Field(max_length=500);keywords:str=Field(max_length=1000);canonical_url:str=Field(max_length=500);og_title:str=Field(max_length=200);og_description:str=Field(max_length=500);og_image:str=Field(max_length=1000);robots:str=Field(pattern=r"^(index|noindex),(follow|nofollow)$")
    analytics_enabled:bool=False
    google_analytics_id:str=Field(default="",max_length=50)
    google_tag_manager_id:str=Field(default="",max_length=50)
    meta_pixel_id:str=Field(default="",max_length=50)
    yandex_metrika_id:str=Field(default="",max_length=50)
    clarity_project_id:str=Field(default="",max_length=50)

async def values(session):
    saved=await SettingsService(session).get(0,MODULE,"main",{})
    return {**DEFAULTS,**(saved if isinstance(saved,dict) else {})}

@router.get("/public/seo")
async def public_seo(session:AsyncSession=Depends(get_db_session)):return await values(session)

@router.put("/platform/seo")
async def update_seo(payload:SeoUpdate,user:User=Depends(require_superadmin),session:AsyncSession=Depends(get_db_session)):
    await SettingsService(session).set(guild_id=0,module=MODULE,key="main",value=payload.model_dump(),updated_by=user.id)
    return await values(session)
