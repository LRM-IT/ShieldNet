import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

from sqlalchemy.dialects.postgresql.asyncpg import dialect

from app.api.routes.member_inspector import inspect_member
from app.schemas.members import MemberDetailResponse, MemberRoleResponse


def test_inspector_queries_numeric_role_ids_without_losing_snowflake_precision():
    guild_id = 1524298982388662385
    role_id = 1553693785169469460
    member = MemberDetailResponse.model_construct(roles=[
        MemberRoleResponse(discord_role_id=str(role_id), role_name="Member", role_position=1, role_color=0)
    ])
    row = MagicMock()
    row.scalar_one.return_value = SimpleNamespace(id=1, joined_at=None, left_at=None)
    empty = MagicMock()
    empty.scalars.return_value.all.return_value = []
    roles = MagicMock()
    roles.scalars.return_value.all.return_value = [SimpleNamespace(permissions=1 << 10)]
    session = SimpleNamespace(execute=AsyncMock(side_effect=[row, empty, empty, empty, roles]))
    with patch("app.api.routes.member_inspector.require_guild_management", new_callable=AsyncMock), patch(
        "app.api.routes.member_inspector.MemberService"
    ) as service:
        service.return_value.get = AsyncMock(return_value=member)
        result = asyncio.run(inspect_member(guild_id, 123, 100, SimpleNamespace(), session))

    query = session.execute.call_args.args[0].compile(
        dialect=dialect(), compile_kwargs={"render_postcompile": True}
    )
    assert "VARCHAR" not in str(query)
    assert role_id in query.params.values()
    assert str(role_id) not in query.params.values()
    assert result.permissions == ["View channels"]
