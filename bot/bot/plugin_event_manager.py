from __future__ import annotations
from datetime import datetime
import discord,httpx
from bot.config import settings
class EventView(discord.ui.View):
 def __init__(self,event_id):
  super().__init__(timeout=None)
  for label,status,style,emoji in[("Going","going",discord.ButtonStyle.success,"✅"),("Maybe","maybe",discord.ButtonStyle.primary,"❔"),("Decline","declined",discord.ButtonStyle.secondary,"✖")]:self.add_item(discord.ui.Button(label=label,style=style,emoji=emoji,custom_id=f"gc-event:{event_id}:{status}"))
class EventManager:
 def __init__(self,bot):self.bot=bot;self.base=settings.backend_url.rstrip("/")+"/api/v1/internal/plugin-event-manager";self.headers={"X-ShieldNet-Service-Token":settings.internal_service_token}
 async def request(self,method,path,**kwargs):
  async with httpx.AsyncClient(timeout=30)as client:r=await client.request(method,f"{self.base}{path}",headers=self.headers,**kwargs);r.raise_for_status();return r.json()
 async def config(self,guild_id):return await self.request("GET",f"/guilds/{guild_id}/configuration")
 @staticmethod
 def embed(event):
  participants=event.get("participants")or{};going=sum(x=="going"for x in participants.values());maybe=sum(x=="maybe"for x in participants.values());start=int(datetime.fromisoformat(str(event["starts_at"]).replace("Z","+00:00")).timestamp());limit=f"/{event['max_participants']}"if event.get("max_participants")else""
  embed=discord.Embed(title=event["title"],description=event.get("description")or"",colour=discord.Colour.teal());embed.add_field(name="Starts",value=f"<t:{start}:F>\n<t:{start}:R>");embed.add_field(name="Participants",value=f"✅ {going}{limit}\n❔ {maybe}");embed.set_footer(text="Use the buttons below to update your RSVP.");return embed
 async def publish(self,guild,event_id):
  cfg=await self.config(guild.id);event=next((x for x in cfg.get("events",[])if x["id"]==event_id),None)
  if not cfg.get("enabled")or not event:raise RuntimeError("Event unavailable")
  channel=guild.get_channel(int(event["channel_id"]));
  if not isinstance(channel,(discord.TextChannel,discord.Thread)):raise RuntimeError("Event channel not found")
  old=event.get("message_id")
  if old:
   try:message=await channel.fetch_message(int(old));await message.edit(embed=self.embed(event),view=EventView(event_id))
   except(discord.NotFound,discord.Forbidden):message=await channel.send(embed=self.embed(event),view=EventView(event_id))
  else:message=await channel.send(embed=self.embed(event),view=EventView(event_id))
  await self.request("POST","/panel",json={"guild_id":guild.id,"event_id":event_id,"channel_id":str(channel.id),"message_id":str(message.id)});return message
 async def handle(self,interaction):
  custom=str((interaction.data or{}).get("custom_id")or"")
  if not custom.startswith("gc-event:"):return False
  _,event_id,status=custom.split(":",2)
  try:result=await self.request("POST","/rsvp",json={"guild_id":interaction.guild_id,"event_id":event_id,"discord_user_id":interaction.user.id,"status":status})
  except httpx.HTTPStatusError as exc:
   text="Event is full."if exc.response.status_code==409 else"Event is unavailable.";await interaction.response.send_message(text,ephemeral=True);return True
  cfg=await self.config(interaction.guild_id);event=next(x for x in cfg["events"]if x["id"]==event_id);await interaction.response.edit_message(embed=self.embed(event),view=EventView(event_id));await interaction.followup.send("Your RSVP was updated.",ephemeral=True);return True
 async def reminders(self):
  data=await self.request("GET","/reminders")
  for event in data.get("events",[]):
   guild=self.bot.get_guild(int(event["guild_id"]));channel=guild.get_channel(int(event["channel_id"]))if guild else None
   if isinstance(channel,(discord.TextChannel,discord.Thread)):
    going=[f"<@{uid}>"for uid,state in(event.get("participants")or{}).items()if state=="going"]
    await channel.send(f"⏰ **{event['title']}** starts soon. "+(" ".join(going)if going else""),allowed_mentions=discord.AllowedMentions(users=True))
