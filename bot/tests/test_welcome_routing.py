import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

from bot.plugin_welcome import WelcomeWorker


def test_worker_requests_only_managed_guilds():
    bot = SimpleNamespace(managed_guilds=[SimpleNamespace(id=1511282749049147482)])
    response = MagicMock()
    response.json.return_value = {"item": None}
    client = AsyncMock()
    client.get.return_value = response
    with patch("bot.plugin_welcome.httpx.AsyncClient") as factory:
        factory.return_value.__aenter__ = AsyncMock(return_value=client)
        factory.return_value.__aexit__ = AsyncMock()
        asyncio.run(WelcomeWorker(bot).run_once())
    assert client.get.call_args.kwargs["params"] == [("guild_id", "1511282749049147482")]


def test_worker_without_guilds_does_not_poll_global_queue():
    with patch("bot.plugin_welcome.httpx.AsyncClient") as factory:
        asyncio.run(WelcomeWorker(SimpleNamespace(managed_guilds=[])).run_once())
    factory.assert_not_called()
