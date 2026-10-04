import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch
import discord
from bot.plugin_first_introduction import LanguageSelection


def test_panel_only_publishes_languages_with_roles():
    async def check():
        message = SimpleNamespace(id=123, add_reaction=AsyncMock(), delete=AsyncMock())
        channel = MagicMock(spec=discord.TextChannel)
        channel.guild = SimpleNamespace(id=456)
        channel.send = AsyncMock(return_value=message)
        guild = SimpleNamespace(id=456, get_channel_or_thread=lambda _: channel)
        worker = LanguageSelection(SimpleNamespace())
        worker.configuration = AsyncMock(return_value={"enabled": True,
            "groups": [{"id": "test", "name": "Test", "enabled": True, "channel_id": "789", "language_roles": {"en": "111"}}],
            "languages": [{"code": "en", "name": "English", "flag": "🇬🇧"}, {"code": "de", "name": "German", "flag": "🇩🇪"}]})
        response = MagicMock()
        client = AsyncMock()
        client.post.return_value = response
        with patch("bot.plugin_first_introduction.httpx.AsyncClient") as factory:
            factory.return_value.__aenter__.return_value = client
            await worker.publish_panel(guild, "test")
        assert "English" in channel.send.call_args.args[0]
        assert "German" not in channel.send.call_args.args[0]
        message.add_reaction.assert_awaited_once_with("🇬🇧")
    asyncio.run(check())
