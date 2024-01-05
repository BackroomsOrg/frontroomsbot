import discord
from discord import app_commands
from discord.ext import commands
from random import choices, randint, uniform

from bot import BackroomsBot


class RandomUtilsCog(commands.Cog):
    def __init__(self, bot: BackroomsBot) -> None:
        self.bot = bot

    @app_commands.command(name="roll", description="Rolls a number")
    async def roll(
        self, interaction: discord.Interaction, first: int = 100, second: int = None
    ):
        if second is None:
            result = randint(0, first)

        else:
            if second < first:
                await interaction.response.send_message(
                    "Second needs to be higher than first."
                )
                return
            result = randint(first, second)

        await interaction.response.send_message(f"{result}")

    @app_commands.command(name="flip", description="Flips a coin")
    async def flip(self, interaction: discord.Interaction):
        # randint(0, 1) ? "True" : "False" <- same thing
        result = "True" if randint(0, 1) else "False"
        await interaction.response.send_message(f"{result}")

    @app_commands.checks.cooldown(1, 60.0)
    @app_commands.command(name="kasparek", description="Zjistí jakého máš kašpárka")
    async def kasparek(self, interaction: discord.Interaction):
        unit = choices(["cm", "mm"], weights=(95, 5), k=1)[0]
        result = round(uniform(0, 50), 2)

        message = f"{result}{unit}" if unit else f"{result}"
        await interaction.response.send_message(message)

    @kasparek.error
    async def on_kasparek_error(
        self, interaction: discord.Interaction, error: app_commands.AppCommandError
    ):
        if isinstance(error, app_commands.CommandOnCooldown):
            await interaction.response.send_message(str(error), ephemeral=True)


async def setup(bot: BackroomsBot) -> None:
    await bot.add_cog(RandomUtilsCog(bot), guild=bot.backrooms)
