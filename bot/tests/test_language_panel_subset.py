import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch
import discord
from bot.plugin_first_introduction import LanguageSelection


def test_panel_only_publishes_languages_with_roles():
    async def check():
        message = SimpleNamespace(id=123, reactions=[], add_reaction=AsyncMock(), delete=AsyncMock())
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



def test_panel_update_preserves_message_and_existing_reactions():
    async def check():
        message = SimpleNamespace(id=123, reactions=[SimpleNamespace(emoji="🇬🇧", me=True)],
            edit=AsyncMock(), add_reaction=AsyncMock(), clear_reaction=AsyncMock(), delete=AsyncMock())
        channel = MagicMock(spec=discord.TextChannel)
        channel.guild = SimpleNamespace(id=456)
        channel.fetch_message = AsyncMock(return_value=message)
        channel.send = AsyncMock()
        guild = SimpleNamespace(id=456, get_channel_or_thread=lambda _: channel)
        worker = LanguageSelection(SimpleNamespace())
        worker.configuration = AsyncMock(return_value={"enabled": True,
            "groups": [{"id":"test", "name":"Test", "enabled":True, "channel_id":"789", "message_id":"123", "language_roles":{"en":"111", "de":"222"}}],
            "languages": [{"code":"en", "name":"English", "flag":"🇬🇧"}, {"code":"de", "name":"German", "flag":"🇩🇪"}]})
        client = AsyncMock()
        client.post.return_value = MagicMock()
        with patch("bot.plugin_first_introduction.httpx.AsyncClient") as factory:
            factory.return_value.__aenter__.return_value = client
            await worker.publish_panel(guild,"test")
            channel.send.assert_not_awaited()
            message.edit.assert_awaited_once()
            message.add_reaction.assert_awaited_once_with("🇩🇪")
            message.clear_reaction.assert_not_awaited()
            message.delete.assert_not_awaited()
            client.post.side_effect = RuntimeError("Backend unavailable")
            try:
                await worker.publish_panel(guild,"test")
            except RuntimeError:
                pass
            else:
                raise AssertionError("Expected failure")
            message.delete.assert_not_awaited()
    asyncio.run(check())
