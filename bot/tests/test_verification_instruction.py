import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock
import discord
from bot.discord_management import DiscordManagementWorker
from bot.plugin_channel_cleanup import ChannelCleanup


async def check_publication():
    channel = MagicMock(spec=discord.TextChannel)
    channel.id = 456
    message = SimpleNamespace(id=789, author=SimpleNamespace(id=111), edit=AsyncMock())
    channel.send = AsyncMock(return_value=message)
    channel.fetch_message = AsyncMock(return_value=message)
    guild = SimpleNamespace(get_channel_or_thread=lambda channel_id: channel)
    bot = SimpleNamespace(get_guild=lambda guild_id: guild, user=SimpleNamespace(id=111), verification=SimpleNamespace())
    worker = DiscordManagementWorker(bot)
    worker._post = AsyncMock()
    item = {"id":"job", "guild_id":123, "object_type":"verification_instruction", "operation":"publish",
            "payload":{"channel_id":"456", "text":"Run /verify to begin."}}
    await worker._process_change(item)
    assert channel.send.call_args.kwargs["view"].is_persistent()
    assert channel.send.call_args.kwargs["embed"].description == "Run /verify to begin."
    assert worker._post.call_args.args[1]["data"] == {"message_id":"789", "channel_id":"456"}
    item["payload"]["message_id"] = "789"
    await worker._process_change(item)
    assert channel.send.await_count == 1
    message.edit.assert_awaited_once()


def test_instruction_publication_edits_existing_message():
    asyncio.run(check_publication())


def test_cleanup_preserves_excluded_message_even_when_unpinned():
    channel = SimpleNamespace(purge=AsyncMock(return_value=[]))
    asyncio.run(ChannelCleanup._purge(channel, discord.utils.utcnow(), False, {"1520855507760316436"}))
    check = channel.purge.call_args.kwargs["check"]
    assert not check(SimpleNamespace(id=1520855507760316436, pinned=False))
    assert check(SimpleNamespace(id=1520855507760316437, pinned=False))


def test_public_button_loads_current_fields_and_preserves_shared_message():
    from bot.verification import VerificationPublicView
    async def check():
        client = SimpleNamespace(settings=AsyncMock(return_value={"enabled": True, "nickname_template": "{nickname}"}))
        view = VerificationPublicView(client)
        response = SimpleNamespace(send_modal=AsyncMock(), send_message=AsyncMock(), is_done=lambda: False)
        interaction = SimpleNamespace(guild_id=123, response=response)
        await view.children[0].callback(interaction)
        modal = response.send_modal.call_args.args[0]
        assert modal.prompt_message is None
        assert modal.from_public_button
        assert [field.label for field in modal.children] == ["Nickname"]
        assert view.is_persistent()
        client.settings.return_value = {"enabled": False}
        response.send_modal.reset_mock()
        await view.children[0].callback(interaction)
        response.send_modal.assert_not_awaited()
        response.send_message.assert_awaited_once()
    asyncio.run(check())
