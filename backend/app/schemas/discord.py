from pydantic import BaseModel, Field
class GuildRegisterRequest(BaseModel):
    guild_id:int=Field(gt=0); name:str=Field(min_length=1,max_length=255); icon_url:str|None=None
    owner_discord_id:int=Field(gt=0); member_count:int=Field(default=0,ge=0); preferred_language:str='uk'
class GuildLeftRequest(BaseModel): guild_id:int=Field(gt=0)
class GuildReconcileRequest(BaseModel): guild_ids:list[int]=Field(default_factory=list)
class GuildAccessResponse(BaseModel):
    guild_id: str
    name: str
    icon_url: str | None
    owner_discord_id: str
    member_count: int
    guild_status: str
    bot_status: str
    access_role: str
    permissions: list[str] = []
    expires_at: str | None = None
    is_owner: bool = False
    billing_status: str = "inactive"
    billing_expires_at: str | None = None
    billing_auto_renew: bool = False
    last_sync_at: str | None = None
    sync_status: str = "never"
    enabled_plugins: int = 0
    custom_bot_active: bool = False
