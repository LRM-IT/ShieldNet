from __future__ import annotations
import logging
import discord
import httpx
from bot.config import settings

logger=logging.getLogger(__name__)

def emoji_value(raw:str):
    if not raw: return None
    try: return discord.PartialEmoji.from_str(raw)
    except Exception: return None

class RoleMenuSelect(discord.ui.Select):
    def __init__(self,panel:dict):
        options=[]
        for item in panel.get("options",[]):
            options.append(discord.SelectOption(label=item["label"],value=item["role_id"],description=item.get("description") or None,emoji=emoji_value(item.get("emoji") or "")))
        max_values=min(len(options),panel.get("max_roles") or len(options))
        super().__init__(placeholder="Choose roles",min_values=0,max_values=max(1,max_values),options=options,custom_id=f"gc-role-select:{panel['id']}")

class RoleMenuView(discord.ui.View):
    def __init__(self,panel:dict):
        super().__init__(timeout=None)
        if panel.get("mode")=="select": self.add_item(RoleMenuSelect(panel)); return
        for index,item in enumerate(panel.get("options",[])):
            button=discord.ui.Button(label=item["label"],emoji=emoji_value(item.get("emoji") or ""),style=discord.ButtonStyle.secondary,custom_id=f"gc-role:{panel['id']}:{item['role_id']}",row=index//5)
            self.add_item(button)

class RoleMenu:
    def __init__(self,bot):
        self.bot=bot; self.base=settings.backend_url.rstrip("/")+"/api/v1/internal/plugin-role-menu"; self.headers={"X-ShieldNet-Service-Token":settings.internal_service_token}
    async def config(self,guild_id:int)->dict:
        async with httpx.AsyncClient(timeout=20) as client:
            response=await client.get(f"{self.base}/guilds/{guild_id}/configuration",headers=self.headers); response.raise_for_status(); return response.json()
    async def publish_panel(self,guild:discord.Guild,panel_id:str)->discord.Message:
        config=await self.config(guild.id); panel=next((x for x in config.get("panels",[]) if x["id"]==panel_id and x.get("enabled")),None)
        if not config.get("enabled") or not panel: raise RuntimeError("Role Menu panel is disabled")
        channel=guild.get_channel(int(panel["channel_id"]))
        if not isinstance(channel,(discord.TextChannel,discord.Thread)): raise RuntimeError("Role Menu channel not found")
        old_id=panel.get("message_id")
        if old_id:
            try: await (await channel.fetch_message(int(old_id))).delete()
            except (discord.NotFound,discord.Forbidden): pass
        embed=discord.Embed(title=panel["title"],description=panel.get("description") or "Choose your roles.",colour=discord.Colour.teal())
        message=await channel.send(embed=embed,view=RoleMenuView(panel))
        async with httpx.AsyncClient(timeout=20) as client:
            response=await client.post(f"{self.base}/panel",headers=self.headers,json={"guild_id":guild.id,"panel_id":panel_id,"channel_id":str(channel.id),"message_id":str(message.id)}); response.raise_for_status()
        return message
    async def handle(self,interaction:discord.Interaction)->bool:
        custom_id=str((interaction.data or {}).get("custom_id") or "")
        if not custom_id.startswith("gc-role"): return False
        if interaction.guild is None or not isinstance(interaction.user,discord.Member):
            await interaction.response.send_message("Server only.",ephemeral=True); return True
        config=await self.config(interaction.guild.id)
        parts=custom_id.split(":"); panel_id=parts[1] if len(parts)>1 else ""
        panel=next((x for x in config.get("panels",[]) if x["id"]==panel_id and x.get("enabled") and str(x.get("message_id"))==str(interaction.message.id)),None)
        if not config.get("enabled") or not panel:
            await interaction.response.send_message("This role menu is no longer active.",ephemeral=True); return True
        required=panel.get("required_role_id")
        if required and not any(str(role.id)==required for role in interaction.user.roles):
            await interaction.response.send_message("You do not have the role required to use this menu.",ephemeral=True); return True
        allowed={str(x["role_id"]):x for x in panel.get("options",[])}
        if custom_id.startswith("gc-role-select:"):
            requested={str(x) for x in (interaction.data or {}).get("values",[]) if str(x) in allowed}
            current={str(role.id) for role in interaction.user.roles if str(role.id) in allowed}
            add_ids=requested-current; remove_ids=current-requested
        else:
            role_id=parts[2] if len(parts)>2 else ""
            if role_id not in allowed:
                await interaction.response.send_message("This role is unavailable.",ephemeral=True); return True
            current={str(role.id) for role in interaction.user.roles if str(role.id) in allowed}
            if role_id in current: add_ids=set(); remove_ids={role_id}
            else:
                limit=int(panel.get("max_roles") or 0)
                if limit and len(current)>=limit:
                    await interaction.response.send_message(f"You can select up to {limit} role(s) in this menu.",ephemeral=True); return True
                add_ids={role_id}; remove_ids=set()
        me=interaction.guild.me; add=[]; remove=[]
        for role_id in add_ids:
            role=interaction.guild.get_role(int(role_id))
            if role and me and not role.managed and role<me.top_role: add.append(role)
        for role_id in remove_ids:
            role=interaction.guild.get_role(int(role_id))
            if role and me and not role.managed and role<me.top_role: remove.append(role)
        if add: await interaction.user.add_roles(*add,reason="GuildConsole Role Menu")
        if remove: await interaction.user.remove_roles(*remove,reason="GuildConsole Role Menu")
        names=[role.name for role in add]; removed=[role.name for role in remove]
        text=("Added: "+", ".join(names) if names else "")+(("\n" if names else "")+"Removed: "+", ".join(removed) if removed else "")
        await interaction.response.send_message(text or "Roles are unchanged.",ephemeral=True); return True
