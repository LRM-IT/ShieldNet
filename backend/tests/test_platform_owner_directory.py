import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

from fastapi import HTTPException

from app.api.routes.platform_users import get_server_owner, list_server_owners


def result(items):
    value = MagicMock()
    value.scalars.return_value.all.return_value = items
    value.scalar_one_or_none.return_value = items[0] if items else None
    return value


def guild(guild_id, owner_id):
    return SimpleNamespace(guild_id=guild_id, owner_discord_id=owner_id, name=f"Server {guild_id}",
                           icon_url=None, status=SimpleNamespace(value="active"), bot_status=SimpleNamespace(value="online"))


def test_directory_includes_unregistered_owners_and_groups_their_servers():
    guilds = [guild(1, 101), guild(2, 102), guild(3, 102), guild(4, 103)]
    user = SimpleNamespace(id=uuid4(), discord_user_id=101, display_name="Registered", login="registered",
                           email="owner@example.com", email_verified=True, avatar_url=None,
                           status=SimpleNamespace(value="active"), preferred_locale=None, last_login_at=None, created_at=None)
    member = SimpleNamespace(discord_user_id=102, username="new_owner", global_name="New owner", avatar_url=None)

    def session():
        return SimpleNamespace(execute=AsyncMock(side_effect=[result(guilds), result([]), result([user]), result([member])]))

    response = asyncio.run(list_server_owners("", user, session()))
    assert response["total"] == 3
    by_id = {item["discord_user_id"]: item for item in response["items"]}
    assert by_id["101"]["registered"] is True
    assert by_id["102"]["id"] == "discord:102"
    assert by_id["102"]["display_name"] == "New owner"
    assert len(by_id["102"]["guilds"]) == 2
    assert by_id["102"]["email"] is None
    assert by_id["102"]["registered"] is False
    assert by_id["103"]["display_name"] == "103"
    filtered = asyncio.run(list_server_owners("NEW_OWNER", user, session()))
    assert [item["discord_user_id"] for item in filtered["items"]] == ["102"]


def test_discord_owner_profile_requires_an_owned_synced_server():
    session = SimpleNamespace(execute=AsyncMock(side_effect=[result([]), result([])]))
    try:
        asyncio.run(get_server_owner("discord:102", None, session))
    except HTTPException as exc:
        assert exc.status_code == 404
    else:
        raise AssertionError("An unrelated Discord ID must not have an owner profile")


def test_discord_owner_profile_without_panel_account():
    member = SimpleNamespace(username="owner", global_name="Owner", avatar_url=None)
    session = SimpleNamespace(execute=AsyncMock(side_effect=[result([]), result([guild(1, 102)]), result([]), result([member])]))
    profile = asyncio.run(get_server_owner("discord:102", None, session))
    assert profile["registered"] is False
    assert profile["display_name"] == "Owner"
    assert profile["created_at"] is None
