import asyncio
import logging
from bot.client import ShieldNetBot
from bot.config import settings
from bot.backend import BackendClient

logger = logging.getLogger(__name__)

async def load_custom_bots() -> list[dict]:
    try:return await BackendClient().active_custom_bots()
    except Exception:
        logger.exception("Unable to load active custom bots")
        return []

def fingerprint(rows:list[dict]):return tuple(sorted((str(x["guild_id"]),x["token"]) for x in rows))

async def main() -> None:
    logging.basicConfig(
        level=getattr(logging, settings.log_level.upper(), logging.INFO),
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    while True:
        rows=await load_custom_bots();excluded={int(x["guild_id"]) for x in rows}
        bots=[(ShieldNetBot(excluded_guild_ids=excluded),settings.discord_bot_token)]
        bots += [(ShieldNetBot(target_guild_id=int(x["guild_id"])),x["token"]) for x in rows]
        tasks=[asyncio.create_task(bot.start(token)) for bot,token in bots]
        logger.info("Bot routing generation started: custom_guilds=%s",sorted(excluded))
        try:
            while True:
                await asyncio.sleep(30)
                current=await load_custom_bots()
                if fingerprint(current)!=fingerprint(rows):break
        finally:
            await asyncio.gather(*(bot.close() for bot,_ in bots),return_exceptions=True)
            await asyncio.gather(*tasks,return_exceptions=True)

if __name__ == "__main__":
    asyncio.run(main())
