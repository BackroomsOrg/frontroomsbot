import discord
from discord import app_commands
from discord.ext import commands


class MyCog(commands.Cog):
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

    @app_commands.command(name="hello", description="Sends hello!")
    async def hello(self, interaction: discord.Interaction):
        await interaction.response.send_message("Hello!")


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(MyCog(bot))
