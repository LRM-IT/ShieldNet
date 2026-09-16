import discord
class CrossGuildNetwork:
 def __init__(self,bot):self.bot=bot
 async def announce(self,guild,data):
  channel=guild.get_channel(int(data["channel_id"]))
  if not isinstance(channel,(discord.TextChannel,discord.Thread)):raise RuntimeError("Network announcement channel not found")
  embed=discord.Embed(title=data["title"],description=data["message"],colour=discord.Colour.teal());embed.set_author(name=data["network_name"]);embed.set_footer(text="Cross-Guild Network announcement");return await channel.send(embed=embed)
