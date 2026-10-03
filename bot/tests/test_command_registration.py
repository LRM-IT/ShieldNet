import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock

import discord
from discord.ext import tasks

from bot.client import ShieldNetBot


async def check_command_registration():
    bot = ShieldNetBot()
    expected = {command.name for command in bot.tree.get_commands()}
    assert "verify" in expected and len(expected) > 1
    bot.tree.clear_commands(guild=None)
    bot.tree.sync = AsyncMock()
    bot.verification.settings = AsyncMock(return_value={"slash_command_name": "verify"})
    guild = SimpleNamespace(id=123)
    ref = discord.Object(id=guild.id)
    await bot._sync_verification_command(guild)
    assert {command.name for command in bot.tree.get_commands(guild=ref)} == expected
    await bot._sync_verification_command(guild)
    assert bot.tree.sync.await_count == 1
    bot.verification.settings.return_value = {"slash_command_name": "introduce"}
    await bot._sync_verification_command(guild)
    assert (expected - {"verify"}) | {"introduce"} == {command.name for command in bot.tree.get_commands(guild=ref)}
    bot.verification.settings.return_value = {"slash_command_name": "register"}
    bot.tree.sync.side_effect = RuntimeError("Temporary Discord failure")
    try:
        await bot._sync_verification_command(guild)
    except RuntimeError:
        pass
    else:
        raise AssertionError("Expected sync failure")
    assert bot._verification_slash_commands[guild.id] == "introduce"
    bot.tree.sync.side_effect = None
    await bot._sync_verification_command(guild)
    assert (expected - {"verify"}) | {"register"} == {command.name for command in bot.tree.get_commands(guild=ref)}
    bot.verification.settings.return_value = {"slash_command_name": "verify"}
    await bot._sync_verification_command(guild)
    assert expected == {command.name for command in bot.tree.get_commands(guild=ref)}
    # A second guild may start with a custom name after global templates are cleared.
    bot.verification.settings.return_value = {"slash_command_name": "join"}
    await bot._sync_verification_command(SimpleNamespace(id=456))
    assert (expected - {"verify"}) | {"join"} == {command.name for command in bot.tree.get_commands(guild=discord.Object(id=456))}
    assert expected == {command.name for command in bot.tree.get_commands(guild=ref)}

    @tasks.loop(seconds=3600)
    async def worker():
        await asyncio.sleep(3600)

    bot.test_loop = worker
    task = worker.start()
    await bot.close()
    assert task.done()
    assert not worker.is_running()


def test_new_guild_keeps_commands_after_global_cleanup_and_workers_stop():
    asyncio.run(check_command_registration())
