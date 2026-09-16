import asyncio
import httpx
import discord
from bot.config import settings

class DiscordManagementWorker:
    def __init__(self, bot):
        self.bot = bot
        self.base_url = settings.backend_url.rstrip("/")
        self.headers = {"X-ShieldNet-Service-Token": settings.internal_service_token}

    async def run_once(self):
        async with httpx.AsyncClient(timeout=30) as client:
            response = await client.get(f"{self.base_url}/api/v1/internal/discord-management/pending", headers=self.headers)
            response.raise_for_status()
            payload = response.json()
        for item in payload.get("changes", []):
            await self._process_change(item)
        for item in payload.get("bulk_roles", []):
            await self._process_bulk(item)

    async def _post(self, path, payload):
        async with httpx.AsyncClient(timeout=30) as client:
            response = await client.post(f"{self.base_url}{path}", headers=self.headers, json=payload)
            response.raise_for_status()

    async def _process_change(self, item):
        try:
            guild = self.bot.get_guild(int(item["guild_id"]))
            if guild is None: raise RuntimeError("Guild not available")
            kind, op, target_id, data = item["object_type"], item["operation"], item.get("target_id"), item.get("payload") or {}
            result = {}
            if kind == "language_panel" and op == "publish":
                message = await self.bot.language_selection.publish_panel(guild, data["group_id"])
                result = {"message_id": str(message.id), "channel_id": str(message.channel.id)}
            elif kind == "role_menu_panel" and op == "publish":
                message = await self.bot.role_menu.publish_panel(guild, data["panel_id"])
                result = {"message_id": str(message.id), "channel_id": str(message.channel.id)}
            elif kind == "event_panel" and op == "publish":
                message = await self.bot.event_manager.publish(guild, data["event_id"])
                result = {"message_id": str(message.id), "channel_id": str(message.channel.id)}
            elif kind == "role":
                role = guild.get_role(int(target_id)) if target_id else None
                if op == "create":
                    name=data.get("name", "New role")
                    if data.get("reuse_existing"):
                        role=next((candidate for candidate in guild.roles if candidate.name.casefold()==name.casefold()
                                   and not candidate.managed and candidate < guild.me.top_role), None)
                    if role is None:
                        role = await guild.create_role(name=name, colour=discord.Colour(int(data.get("color", 0))), permissions=discord.Permissions(int(data.get("permissions", 0))), hoist=bool(data.get("hoist", False)), mentionable=bool(data.get("mentionable", False)), reason="GuildConsole language role" if data.get("_plugin")=="first_introduction" else "ShieldNet")
                elif role is None:
                    raise RuntimeError("Role not found")
                elif role.managed or role >= guild.me.top_role:
                    raise RuntimeError("Role cannot be managed by bot")
                elif op == "update":
                    await role.edit(name=data.get("name", role.name), colour=discord.Colour(int(data.get("color", role.colour.value))), permissions=discord.Permissions(int(data.get("permissions", role.permissions.value))), hoist=bool(data.get("hoist", role.hoist)), mentionable=bool(data.get("mentionable", role.mentionable)), reason="ShieldNet")
                elif op == "delete":
                    await role.delete(reason="ShieldNet")
                result = {"role_id": role.id if role else target_id}
            else:
                channel = guild.get_channel(int(target_id)) if target_id else None
                if op == "create":
                    if kind == "category":
                        channel = await guild.create_category(data.get("name", "New category"), reason="ShieldNet")
                    else:
                        category = guild.get_channel(int(data["parent_id"])) if data.get("parent_id") else None
                        ctype = data.get("channel_type", "text")
                        channel = await (guild.create_voice_channel(data.get("name", "new-channel"), category=category, reason="ShieldNet") if ctype == "voice" else guild.create_text_channel(data.get("name", "new-channel"), category=category, topic=data.get("topic"), nsfw=bool(data.get("nsfw", False)), reason="ShieldNet"))
                elif channel is None:
                    raise RuntimeError("Channel not found")
                elif op == "update":
                    kwargs = {k: v for k, v in {"name": data.get("name"), "position": data.get("position"), "topic": data.get("topic"), "nsfw": data.get("nsfw")}.items() if v is not None}
                    await channel.edit(reason="ShieldNet", **kwargs)
                elif op == "delete":
                    await channel.delete(reason="ShieldNet")
                result = {"channel_id": channel.id if channel else target_id}
            await self._post(f"/api/v1/internal/discord-management/changes/{item['id']}/result", {"status": "completed", "data": result})
        except Exception as exc:
            await self._post(f"/api/v1/internal/discord-management/changes/{item['id']}/result", {"status": "failed", "message": str(exc), "data": {}})

    async def _process_bulk(self, item):
        processed, failed, errors = 0, 0, {}
        try:
            guild = self.bot.get_guild(int(item["guild_id"]))
            if guild is None: raise RuntimeError("Guild not available")
            role = guild.get_role(int(item["discord_role_id"]))
            if role is None: raise RuntimeError("Role not found")
            if role.managed or role >= guild.me.top_role: raise RuntimeError("Role cannot be managed by bot")
            for member_id in item.get("member_ids", []):
                try:
                    member = guild.get_member(int(member_id)) or await guild.fetch_member(int(member_id))
                    if item["operation"] == "add": await member.add_roles(role, reason="ShieldNet bulk operation")
                    else: await member.remove_roles(role, reason="ShieldNet bulk operation")
                    processed += 1
                except Exception as exc:
                    failed += 1; errors[str(member_id)] = str(exc)
                await asyncio.sleep(.15)
            await self._post(f"/api/v1/internal/discord-management/bulk-roles/{item['id']}/result", {"status": "completed" if failed == 0 else "failed", "processed_count": processed, "failed_count": failed, "result": {"errors": errors}})
        except Exception as exc:
            await self._post(f"/api/v1/internal/discord-management/bulk-roles/{item['id']}/result", {"status": "failed", "processed_count": processed, "failed_count": failed, "result": {"error": str(exc), "errors": errors}})
