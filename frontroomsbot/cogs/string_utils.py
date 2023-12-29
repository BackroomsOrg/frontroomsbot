import discord
from discord.ext import commands
from discord import app_commands

from ..bot import BackroomsBot

class StringUtilsCog(commands.Cog):
    def __init__(self, bot: BackroomsBot) -> None:
        self.bot = bot
    
    @app_commands.command(name="mock", description="Mocks a message")
    async def mock(interaction: discord.Interaction, message: str):
        result = ""
        for i, c in enumerate(message):
            new_c = c
            if c.isalpha():
                new_c = c.upper() if i % 2 == 0 else c.lower()

            result += new_c

        await interaction.response.send_message(f"{result}")


async def setup(bot: ) -> None:
