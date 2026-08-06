from contextlib import asynccontextmanager
from typing import AsyncIterator

from fastapi import FastAPI

from app.api.router import api_router
from app.api.routes.global_languages import router as global_languages_router
from app.api.routes.guild_languages import router as guild_languages_router
from app.api.routes.user_languages import router as user_languages_router
from app.api.routes.plugin_antiflood import router as plugin_antiflood_router
from app.api.routes.plugin_voting import router as plugin_voting_router
from app.api.routes.internal_plugin_voting import router as internal_plugin_voting_router
from app.api.routes.template_bank import router as template_bank_router
from app.api.routes.template_renderer import router as template_renderer_router
from app.api.routes.media_assets import router as media_assets_router
from app.core.config import settings
from app.core.events import event_bus
from app.db.session import close_database
from app.plugins.runtime import plugin_runtime


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    await event_bus.start()
    await plugin_runtime.start(app)
    try:
        yield
    finally:
        await plugin_runtime.stop()
        await event_bus.stop()
        await close_database()


app = FastAPI(
    title="ShieldNet API",
    description="Backend API for ShieldNet.",
    version="3.2.2",
    debug=settings.debug,
    lifespan=lifespan,
    docs_url="/docs" if settings.environment != "production" else None,
    redoc_url="/redoc" if settings.environment != "production" else None,
)

app.include_router(plugin_antiflood_router, prefix="/api/v1")
app.include_router(plugin_voting_router, prefix="/api/v1")
app.include_router(internal_plugin_voting_router, prefix="/api/v1")
app.include_router(template_bank_router, prefix="/api/v1")
app.include_router(template_renderer_router, prefix="/api/v1")
app.include_router(media_assets_router, prefix="/api/v1")
app.include_router(global_languages_router, prefix="/api/v1")
app.include_router(guild_languages_router, prefix="/api/v1")
app.include_router(user_languages_router, prefix="/api/v1")
app.include_router(api_router, prefix="/api/v1")


@app.get("/")
async def root() -> dict[str, str]:
    return {
        "service": "ShieldNet API",
        "version": "3.2.2",
        "status": "running",
    }
