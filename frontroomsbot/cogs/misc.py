import discord
from discord.ext import commands
from discord import app_commands

from bot import BackroomsBot


class MiscellaneousCog(commands.Cog):
    def __init__(self, bot: BackroomsBot) -> None:
        self.bot = bot

    @app_commands.command(name="increment", description="Makes a number go up")
    async def increment(self, interaction: discord.Interaction):
        db = self.bot.db
        fld = await db.counting.find_one({"count": {"$exists": True}}) or {"count": 0}
        nfld = fld.copy()
        nfld["count"] += 1
        await db.counting.replace_one(fld, nfld, upsert=True)
        await interaction.response.send_message(str(nfld["count"]))

    @app_commands.command(name="sync", description="Syncs commands")
    async def sync(self, interaction: discord.Interaction):
        print("Syncing commands")
        ret = await self.bot.tree.sync(guild=self.bot.guilds[0])
        print(ret)
        await interaction.response.send_message("Synced!")
        print("Command tree synced")


async def setup(bot: BackroomsBot) -> None:
    await bot.add_cog(MiscellaneousCog(bot), guild=bot.guilds[0])
