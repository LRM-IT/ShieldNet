import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch
from fastapi import HTTPException
from app.api.routes.plugin_first_introduction import publish_language_panel, PublishInput


def test_publish_accepts_subset_and_rejects_empty_selection():
    async def check():
        group = {"id":"test", "name":"Test", "enabled":True, "channel_id":"123456789012345", "access_role_id":"123456789012346", "language_roles":{"en":"123456789012347"}}
        installation = SimpleNamespace(enabled=True, configuration={"groups":[group]})
        session = SimpleNamespace(scalar=AsyncMock(return_value=None), add=lambda item: None, commit=AsyncMock())
        with patch('app.api.routes.plugin_first_introduction.require_guild_module',new=AsyncMock()), patch('app.api.routes.plugin_first_introduction._installation',new=AsyncMock(return_value=installation)), patch('app.api.routes.plugin_first_introduction._languages',new=AsyncMock(return_value=[{"code":"en"},{"code":"de"}])):
            await publish_language_panel(1,PublishInput(group_id='test'),SimpleNamespace(id=None),session)
            session.commit.assert_awaited_once()
            group['language_roles']={}
            try:
                await publish_language_panel(1,PublishInput(group_id='test'),SimpleNamespace(id=None),session)
            except HTTPException as exc:
                assert exc.status_code==422
            else:
                raise AssertionError('Empty selection accepted')
    asyncio.run(check())
