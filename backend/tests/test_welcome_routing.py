import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

from app.api.routes.plugin_welcome import due


def test_unscoped_worker_cannot_claim_welcome_tasks():
    session = SimpleNamespace(execute=AsyncMock())
    assert asyncio.run(due([], session)) == {"item": None}
    session.execute.assert_not_awaited()


def test_welcome_claim_is_limited_to_worker_guilds():
    result = MagicMock()
    result.mappings.return_value.first.return_value = None
    session = SimpleNamespace(execute=AsyncMock(return_value=result))
    guild_ids = [1511282749049147482]
    assert asyncio.run(due(guild_ids, session)) == {"item": None}
    query, params = session.execute.call_args.args
    assert "t.guild_id = ANY(CAST(:guild_ids AS bigint[]))" in str(query)
    assert params == {"guild_ids": guild_ids}
