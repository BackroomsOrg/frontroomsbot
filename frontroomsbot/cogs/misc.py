import discord
from discord.ext import commands
from discord import app_commands
import httpx

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
        ret = await self.bot.tree.sync(guild=self.bot.backrooms)
        print(ret)
        await interaction.response.send_message("Synced!")
        print("Command tree synced")

    @app_commands.command(name="nameday", description="Whose name day is it today?")
    @app_commands.describe(date="Date to get name day for in format YYYY-MM-DD")
    async def nameday(self, interaction: discord.Interaction, date: str | None = None):
        uri = "https://svatkyapi.cz/api/day"
        if date is not None:
            uri += f"/{date}"

        async with httpx.AsyncClient() as ac:
            response = await ac.get(uri)

        if response.status_code == 200:
            json = response.json()
            name = json["name"]
            date_str = f"Dne {date}" if date is not None else "Dnes"

            await interaction.response.send_message(f"{date_str} má svátek {name}")
        else:
            print(response)
            print("Nameday failed")


async def setup(bot: BackroomsBot) -> None:
    await bot.add_cog(MiscellaneousCog(bot), guild=bot.backrooms)
