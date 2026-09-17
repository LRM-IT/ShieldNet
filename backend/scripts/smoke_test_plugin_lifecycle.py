"""Run an isolated install/enable/start/disable/uninstall smoke test."""

from __future__ import annotations

import asyncio
import json
from datetime import UTC, datetime, timedelta
from uuid import uuid4

from sqlalchemy import delete, select

from app.db.session import AsyncSessionFactory, close_database
from app.models.billing import BillingSubscription
from app.models.discord import BotStatus, Guild, GuildStatus
from app.models.plugins import GuildPluginInstallation, PluginRegistry, PluginRuntimeInstance
from app.services.guild_plugin_service import GuildPluginService


TEST_GUILD_ID = 9_223_372_036_854_775_000


async def cleanup() -> None:
    async with AsyncSessionFactory() as session:
        await session.execute(delete(PluginRuntimeInstance).where(PluginRuntimeInstance.guild_id == TEST_GUILD_ID))
        await session.execute(delete(GuildPluginInstallation).where(GuildPluginInstallation.guild_id == TEST_GUILD_ID))
        await session.execute(delete(BillingSubscription).where(BillingSubscription.guild_id == TEST_GUILD_ID))
        guild = await session.get(Guild, TEST_GUILD_ID)
        if guild is not None:
            await session.delete(guild)
        await session.commit()


async def configure_special_plugin(plugin_key: str) -> None:
    async with AsyncSessionFactory() as session:
        row = (
            await session.execute(
                select(GuildPluginInstallation).where(
                    GuildPluginInstallation.guild_id == TEST_GUILD_ID,
                    GuildPluginInstallation.plugin_key == plugin_key,
                )
            )
        ).scalar_one()
        if plugin_key == "first_introduction":
            row.configuration = {
                "groups": [{
                    "enabled": True,
                    "channel_id": "1",
                    "access_role_id": "2",
                    "language_roles": {"en": "3"},
                }]
            }
        elif plugin_key == "translator_groups":
            row.configuration = {
                "groups": [{
                    "enabled": True,
                    "channels": [
                        {"channel_id": "1", "language": "en"},
                        {"channel_id": "2", "language": "uk"},
                    ],
                }]
            }
        await session.commit()


async def main() -> None:
    await cleanup()
    results: list[dict[str, object]] = []
    try:
        async with AsyncSessionFactory() as session:
            session.add(Guild(
                guild_id=TEST_GUILD_ID,
                name="Plugin lifecycle smoke test",
                owner_discord_id=TEST_GUILD_ID,
                member_count=0,
                preferred_language="en",
                status=GuildStatus.ACTIVE,
                bot_status=BotStatus.ONLINE,
            ))
            await session.commit()
            session.add(BillingSubscription(
                id=uuid4(),
                guild_id=TEST_GUILD_ID,
                plugin_key="__paid_modules__",
                status="active",
                billing_period="month",
                starts_at=datetime.now(UTC) - timedelta(minutes=1),
                expires_at=datetime.now(UTC) + timedelta(days=1),
                provider="smoke_test",
                auto_renew=False,
            ))
            await session.commit()
            keys = list((await session.execute(
                select(PluginRegistry.plugin_key)
                .where(PluginRegistry.healthy.is_(True))
                .order_by(PluginRegistry.plugin_key)
            )).scalars())

        for key in keys:
            result: dict[str, object] = {"plugin": key}
            try:
                async with AsyncSessionFactory() as session:
                    await GuildPluginService(session).install(TEST_GUILD_ID, key, None)
                result["install"] = "ok"
                await configure_special_plugin(key)
                async with AsyncSessionFactory() as session:
                    await GuildPluginService(session).set_enabled(TEST_GUILD_ID, key, True)
                result["enable"] = "ok"
                await asyncio.sleep(3)
                async with AsyncSessionFactory() as session:
                    runtime = (await session.execute(select(PluginRuntimeInstance).where(
                        PluginRuntimeInstance.guild_id == TEST_GUILD_ID,
                        PluginRuntimeInstance.plugin_key == key,
                    ))).scalar_one_or_none()
                    result["runtime"] = runtime.state if runtime else "missing"
                    result["runtime_error"] = runtime.last_error if runtime else "runtime row missing"
                    await GuildPluginService(session).set_enabled(TEST_GUILD_ID, key, False)
                result["disable"] = "ok"
                async with AsyncSessionFactory() as session:
                    await GuildPluginService(session).uninstall(TEST_GUILD_ID, key)
                    remaining_install = (await session.execute(select(GuildPluginInstallation).where(
                        GuildPluginInstallation.guild_id == TEST_GUILD_ID,
                        GuildPluginInstallation.plugin_key == key,
                    ))).scalar_one_or_none()
                    remaining_runtime = (await session.execute(select(PluginRuntimeInstance).where(
                        PluginRuntimeInstance.guild_id == TEST_GUILD_ID,
                        PluginRuntimeInstance.plugin_key == key,
                    ))).scalar_one_or_none()
                result["uninstall"] = "ok" if remaining_install is None and remaining_runtime is None else "residue"
            except Exception as exc:
                result["error"] = f"{type(exc).__name__}: {exc}"
            results.append(result)
            print(json.dumps(result, ensure_ascii=False), flush=True)
    finally:
        await cleanup()
        await close_database()

    failed = [item for item in results if item.get("error") or item.get("runtime") != "running" or item.get("uninstall") != "ok"]
    print(json.dumps({"tested": len(results), "failed": len(failed), "failures": failed}, ensure_ascii=False))
    if failed:
        raise SystemExit(1)


if __name__ == "__main__":
    asyncio.run(main())
