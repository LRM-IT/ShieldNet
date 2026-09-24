from fastapi import APIRouter,Depends
from sqlalchemy.ext.asyncio import AsyncSession
from app.api.dependencies.internal import verify_internal_service_token
from app.db.session import get_db_session
from app.schemas.discord import GuildRegisterRequest,GuildLeftRequest,GuildReconcileRequest
from app.services.guild_registration import GuildRegistrationService
router=APIRouter(prefix='/internal/discord',tags=['Internal Discord'],dependencies=[Depends(verify_internal_service_token)])
@router.post('/guilds/register')
async def register_guild(payload:GuildRegisterRequest,session:AsyncSession=Depends(get_db_session)):
    guild=await GuildRegistrationService(session).register(payload); return {'status':'registered','guild_id':guild.guild_id,'name':guild.name}
@router.post('/guilds/left')
async def guild_left(payload:GuildLeftRequest,session:AsyncSession=Depends(get_db_session)):
    await GuildRegistrationService(session).mark_left(payload.guild_id); return {'status':'left','guild_id':payload.guild_id}
@router.post('/guilds/reconcile')
async def reconcile_guilds(payload:GuildReconcileRequest,session:AsyncSession=Depends(get_db_session)):
    removed=await GuildRegistrationService(session).reconcile_connected(payload.guild_ids)
    return {'status':'reconciled','connected':len(payload.guild_ids),'removed':removed}
