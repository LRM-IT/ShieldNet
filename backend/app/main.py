from contextlib import asynccontextmanager
from typing import AsyncIterator

from fastapi import FastAPI

from app.api.router import api_router
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

app.include_router(api_router, prefix="/api/v1")


@app.get("/")
async def root() -> dict[str, str]:
    return {
        "service": "ShieldNet API",
        "version": "3.2.2",
        "status": "running",
    }
