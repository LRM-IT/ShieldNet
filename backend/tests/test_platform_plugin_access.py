import asyncio

import pytest
from fastapi import HTTPException

from app.api.dependencies.platform_access import require_platform_admin, require_platform_viewer
from app.models.core import GlobalRole, User, UserRole


def test_superadmin_discord_session_can_read_platform_plugins() -> None:
    user = User(roles=[UserRole(role=GlobalRole.SUPERADMIN)])
    user._auth_source = "discord_guild"

    assert asyncio.run(require_platform_viewer(user)) is user
    assert asyncio.run(require_platform_admin(user)) is user


def test_regular_discord_session_cannot_read_platform_plugins() -> None:
    user = User(roles=[])
    user._auth_source = "discord_guild"

    with pytest.raises(HTTPException) as exc:
        asyncio.run(require_platform_admin(user))
    assert exc.value.status_code == 403
