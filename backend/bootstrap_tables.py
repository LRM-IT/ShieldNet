import asyncio
from app.db.session import engine
from app.models.core import Base
import app.models.plugin_voting  # noqa

async def main():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

asyncio.run(main())
