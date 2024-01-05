import discord
from discord.ext import commands
from discord import app_commands

from bot import BackroomsBot


class StringUtilsCog(commands.Cog):
    def __init__(self, bot: BackroomsBot) -> None:
        self.bot = bot

    @app_commands.command(name="mock", description="Mocks a message")
    async def mock(self, interaction: discord.Interaction, message: str):
        result = ""
        alpha_cnt = 0
        for c in message:
            new_c = c
            if c.isalpha():
                new_c = c.upper() if alpha_cnt % 2 == 0 else c.lower()
                alpha_cnt += 1

            result += new_c

        await interaction.response.send_message(f"{result}")


async def setup(bot: BackroomsBot) -> None:
    await bot.add_cog(StringUtilsCog(bot), guild=bot.backrooms)
