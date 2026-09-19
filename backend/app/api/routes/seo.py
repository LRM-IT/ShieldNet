from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies.platform_access import require_superadmin
from app.db.session import get_db_session
from app.models.core import User
from app.services.settings import SettingsService

router=APIRouter(tags=["Public SEO"]);MODULE="public_seo"
DEFAULTS={"site_name":"GuildConsole","title":"GuildConsole — керування Discord-серверами","description":"GuildConsole — захищена панель керування Discord-серверами, автоматизацією, безпекою, модерацією та плагінами.","keywords":"Discord, керування Discord сервером, Discord бот, автоматизація Discord, модерація Discord, GuildConsole","canonical_url":"https://guildconsole.lrm-it.com/","og_title":"GuildConsole — контроль Discord-інфраструктури","og_description":"Керуйте Discord-серверами, безпекою, автоматизацією та плагінами з єдиної захищеної панелі.","og_image":"","robots":"index,follow","analytics_enabled":False,"google_analytics_id":"","google_tag_manager_id":"","meta_pixel_id":"","yandex_metrika_id":"","clarity_project_id":""}
SUPPORTED_LOCALES={"en","uk","ru","de","ar","fr","it","pl"}
LOCALIZED={
 "en":{"title":"GuildConsole — Discord server management","description":"A secure control panel for Discord servers, automation, moderation, security and plugins.","keywords":"Discord server management, Discord bot, Discord automation, Discord moderation, GuildConsole","og_title":"GuildConsole — manage your Discord infrastructure","og_description":"Manage Discord servers, security, automation and plugins from one secure dashboard."},
 "uk":{"title":DEFAULTS["title"],"description":DEFAULTS["description"],"keywords":DEFAULTS["keywords"],"og_title":DEFAULTS["og_title"],"og_description":DEFAULTS["og_description"]},
 "ru":{"title":"GuildConsole — управление Discord-серверами","description":"Защищённая панель управления Discord-серверами, автоматизацией, модерацией, безопасностью и плагинами.","keywords":"управление Discord сервером, Discord бот, автоматизация Discord, модерация Discord, GuildConsole","og_title":"GuildConsole — управление Discord-инфраструктурой","og_description":"Управляйте Discord-серверами, безопасностью, автоматизацией и плагинами из единой панели."},
 "de":{"title":"GuildConsole — Discord-Server verwalten","description":"Sichere Verwaltung für Discord-Server, Automatisierung, Moderation, Sicherheit und Plugins.","keywords":"Discord Server verwalten, Discord Bot, Discord Automatisierung, Discord Moderation, GuildConsole","og_title":"GuildConsole — Discord-Infrastruktur verwalten","og_description":"Verwalten Sie Discord-Server, Sicherheit, Automatisierung und Plugins in einem Dashboard."},
 "fr":{"title":"GuildConsole — gestion de serveurs Discord","description":"Tableau de bord sécurisé pour les serveurs Discord, l’automatisation, la modération, la sécurité et les plugins.","keywords":"gestion serveur Discord, bot Discord, automatisation Discord, modération Discord, GuildConsole","og_title":"GuildConsole — gérez votre infrastructure Discord","og_description":"Gérez vos serveurs Discord, la sécurité, l’automatisation et les plugins depuis une seule interface."},
 "it":{"title":"GuildConsole — gestione dei server Discord","description":"Pannello sicuro per server Discord, automazione, moderazione, sicurezza e plugin.","keywords":"gestione server Discord, bot Discord, automazione Discord, moderazione Discord, GuildConsole","og_title":"GuildConsole — gestisci la tua infrastruttura Discord","og_description":"Gestisci server Discord, sicurezza, automazione e plugin da un unico pannello."},
 "pl":{"title":"GuildConsole — zarządzanie serwerami Discord","description":"Bezpieczny panel do obsługi serwerów Discord, automatyzacji, moderacji, bezpieczeństwa i wtyczek.","keywords":"zarządzanie serwerem Discord, bot Discord, automatyzacja Discord, moderacja Discord, GuildConsole","og_title":"GuildConsole — zarządzaj infrastrukturą Discord","og_description":"Zarządzaj serwerami Discord, bezpieczeństwem, automatyzacją i wtyczkami w jednym panelu."},
 "ar":{"title":"GuildConsole — إدارة خوادم Discord","description":"لوحة آمنة لإدارة خوادم Discord والأتمتة والإشراف والأمان والإضافات.","keywords":"إدارة خادم Discord، بوت Discord، أتمتة Discord، إشراف Discord، GuildConsole","og_title":"GuildConsole — إدارة بنية Discord","og_description":"أدر خوادم Discord والأمان والأتمتة والإضافات من لوحة واحدة آمنة."}
}
LOCALIZED_FIELDS={"title","description","keywords","og_title","og_description"}

class SeoUpdate(BaseModel):
    site_name:str=Field(max_length=100);title:str=Field(max_length=200);description:str=Field(max_length=500);keywords:str=Field(max_length=1000);canonical_url:str=Field(max_length=500);og_title:str=Field(max_length=200);og_description:str=Field(max_length=500);og_image:str=Field(max_length=1000);robots:str=Field(pattern=r"^(index|noindex),(follow|nofollow)$")
    analytics_enabled:bool=False
    google_analytics_id:str=Field(default="",max_length=50)
    google_tag_manager_id:str=Field(default="",max_length=50)
    meta_pixel_id:str=Field(default="",max_length=50)
    yandex_metrika_id:str=Field(default="",max_length=50)
    clarity_project_id:str=Field(default="",max_length=50)

async def values(session,locale):
    locale=locale if locale in SUPPORTED_LOCALES else "en"
    service=SettingsService(session);global_saved=await service.get(0,MODULE,"main",{});local_saved=await service.get(0,MODULE,f"main.{locale}",{})
    return {**DEFAULTS,**(global_saved if isinstance(global_saved,dict) else {}),**LOCALIZED[locale],**(local_saved if isinstance(local_saved,dict) else {}),"locale":locale}

@router.get("/public/seo")
async def public_seo(locale:str=Query("en"),session:AsyncSession=Depends(get_db_session)):return await values(session,locale)

@router.put("/platform/seo")
async def update_seo(payload:SeoUpdate,locale:str=Query("en"),user:User=Depends(require_superadmin),session:AsyncSession=Depends(get_db_session)):
    locale=locale if locale in SUPPORTED_LOCALES else "en";data=payload.model_dump();service=SettingsService(session)
    await service.set(guild_id=0,module=MODULE,key="main",value={k:v for k,v in data.items() if k not in LOCALIZED_FIELDS},updated_by=user.id)
    await service.set(guild_id=0,module=MODULE,key=f"main.{locale}",value={k:v for k,v in data.items() if k in LOCALIZED_FIELDS},updated_by=user.id)
    return await values(session,locale)
