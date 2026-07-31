from __future__ import annotations
from fastapi import APIRouter,Depends,HTTPException
from pydantic import BaseModel,Field
from sqlalchemy import delete,select
from sqlalchemy.ext.asyncio import AsyncSession
from app.api.dependencies.auth import get_current_user
from app.api.dependencies.guild_access import require_guild_management
from app.db.session import get_db_session
from app.models.core import User
from app.models.global_languages import GlobalLanguage
from app.models.user_languages import UserLanguage

router=APIRouter(tags=["Language Workspace"])
class Item(BaseModel):
    code:str=Field(min_length=2,max_length=16); enabled:bool=True; is_primary:bool=False; is_fallback:bool=False; sort_order:int=Field(default=100,ge=0,le=10000)
class Update(BaseModel): items:list[Item]

def dump(lang,sel=None):
    return {"id":lang.id,"code":lang.code,"name":lang.name,"native_name":lang.native_name,"flag":lang.flag,"locale":lang.locale,"is_active":lang.is_active,"selected":sel is not None,"enabled":sel.enabled if sel else False,"is_primary":sel.is_primary if sel else False,"is_fallback":sel.is_fallback if sel else False,"sort_order":sel.sort_order if sel else lang.sort_order}

async def catalogue(session,user_id):
    rows=(await session.execute(select(GlobalLanguage,UserLanguage).outerjoin(UserLanguage,(UserLanguage.language_code==GlobalLanguage.code)&(UserLanguage.user_id==user_id)).where(GlobalLanguage.is_active.is_(True)).order_by(UserLanguage.sort_order.nulls_last(),GlobalLanguage.sort_order,GlobalLanguage.name))).all()
    return [dump(a,b) for a,b in rows]

@router.get("/me/languages")
async def mine(user:User=Depends(get_current_user),session:AsyncSession=Depends(get_db_session)):
    return await catalogue(session,user.id)

@router.put("/me/languages")
async def save(payload:Update,user:User=Depends(get_current_user),session:AsyncSession=Depends(get_db_session)):
    active=set((await session.execute(select(GlobalLanguage.code).where(GlobalLanguage.is_active.is_(True)))).scalars())
    if len(payload.items)!=len({x.code for x in payload.items}): raise HTTPException(422,"Duplicate language.")
    invalid=sorted({x.code for x in payload.items}-active)
    if invalid: raise HTTPException(422,f"Unknown languages: {', '.join(invalid)}")
    enabled=[x for x in payload.items if x.enabled]
    if not enabled: raise HTTPException(422,"Select at least one enabled language.")
    if sum(x.is_primary for x in enabled)!=1: raise HTTPException(422,"Select exactly one primary language.")
    if sum(x.is_fallback for x in enabled)!=1: raise HTTPException(422,"Select exactly one fallback language.")
    await session.execute(delete(UserLanguage).where(UserLanguage.user_id==user.id))
    for x in payload.items: session.add(UserLanguage(user_id=user.id,language_code=x.code,enabled=x.enabled,is_primary=x.is_primary,is_fallback=x.is_fallback,sort_order=x.sort_order))
    await session.commit(); return await catalogue(session,user.id)

@router.get("/discord/guilds/{guild_id}/available-languages")
async def available(guild_id:int,user:User=Depends(get_current_user),session:AsyncSession=Depends(get_db_session)):
    await require_guild_management(session,user,guild_id)
    rows=(await session.execute(select(GlobalLanguage,UserLanguage).join(UserLanguage,(UserLanguage.language_code==GlobalLanguage.code)&(UserLanguage.user_id==user.id)).where(GlobalLanguage.is_active.is_(True),UserLanguage.enabled.is_(True)).order_by(UserLanguage.sort_order,GlobalLanguage.name))).all()
    if rows: return [dump(a,b) for a,b in rows]
    defaults=(await session.execute(select(GlobalLanguage).where(GlobalLanguage.is_active.is_(True),GlobalLanguage.code.in_(("en","uk"))).order_by(GlobalLanguage.sort_order))).scalars().all()
    return [{**dump(x),"selected":True,"enabled":True,"is_primary":x.code=="en" or len(defaults)==1,"is_fallback":x.code=="en" or len(defaults)==1} for x in defaults]
