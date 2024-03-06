# should be loaded first and not use the DB or config

import discord
from discord.ext import commands
from discord import app_commands

from bot import BackroomsBot


@app_commands.checks.has_permissions(moderate_members=True)
class MetaCog(commands.GroupCog, group_name="extensions"):
    def __init__(self, bot: BackroomsBot) -> None:
        self.bot = bot

    @app_commands.command(
        name="status", description="List all extensions and their status"
    )
    async def cogs(self, interaction: discord.Interaction):
        all_extensions = set(self.bot.list_extensions())
        loaded_extensions = self.bot.extensions.keys()
        lines = []
        if not (all_extensions >= loaded_extensions):
            lines.append(
                f"found surplus extensions: {loaded_extensions - all_extensions}"
            )
        for ext in sorted(all_extensions):
            char = (
                "\N{WHITE HEAVY CHECK MARK}"
                if ext in loaded_extensions
                else "\N{CROSS MARK}"
            )
            lines.append(f"## {char} {ext}")
            if ext in self.bot.extensions:
                mod = self.bot.extensions[ext]
                for name, v in vars(mod).items():
                    if (
                        isinstance(v, type)
                        and issubclass(v, commands.Cog)
                        and name != "ConfigCog"
                    ):
                        cog_char = (
                            "\N{WHITE HEAVY CHECK MARK}"
                            if self.bot.get_cog(v.__cog_name__)
                            else "\N{CROSS MARK}"
                        )
                        lines.append(f" - {cog_char} {name}")
        await interaction.response.send_message("\n".join(lines))

    @app_commands.command(name="load", description="(re)Load a specific extension")
    async def load(self, interaction: discord.Interaction, ext: str):
        if ext in self.bot.extensions:
            await self.bot.reload_extension(ext)
        else:
            await self.bot.load_extension(ext)
        await interaction.response.send_message(f"Extension {ext} loaded.")

    @app_commands.command(name="unload", description="unload a specific extension")
    async def unload(self, interaction: discord.Interaction, ext: str):
        await self.bot.unload_extension(ext)
        await interaction.response.send_message(f"Extension {ext} loaded.")


async def setup(bot: BackroomsBot) -> None:
    await bot.add_cog(MetaCog(bot), guild=bot.backrooms)
