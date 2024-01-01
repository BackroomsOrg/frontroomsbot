from bot import BackroomsBot
from discord.ext import commands
from discord import app_commands, Interaction
from ._config import ConfigCog, clear_cache, gen_modal


class ConfigCommands(commands.Cog):
    def __init__(self, bot: BackroomsBot) -> None:
        self.bot = bot

    async def cog_autocomplete(self, interaction: Interaction, current: str):
        cogs = ConfigCog.__subclasses__()
        return [
            app_commands.Choice(name=cog.key, value=cog.key)
            for cog in cogs
            if current in cog.key
        ] + [app_commands.Choice(name="purge-cache", value="purge-cache")]

    @app_commands.command(name="config", description="Configure a specific cog")
    @app_commands.checks.has_permissions(moderate_members=True)
    @app_commands.autocomplete(cog_module=cog_autocomplete)
    async def get(self, interaction: Interaction, cog_module: str):
        """/config"""
        if cog_module == "purge-cache":
            clear_cache()
            await interaction.response.send_message("Cache purged", ephemeral=True)
            return
        cogs = ConfigCog.__subclasses__()
        try:
            cog = next(cog for cog in cogs if cog.key == cog_module)
        except StopIteration:
            await interaction.response.send_message(
                "No such configurable cog.", ephemeral=True
            )
        else:
            cog_instance = self.bot.get_cog(cog.__cog_name__)
            if not cog_instance:
                await interaction.response.send_message(
                    "That cog is not loaded", ephemeral=True
                )
            assert isinstance(
                cog_instance, ConfigCog
            ), "Found a non-configurable cog, perhaps two cogs live in the same module"
            await interaction.response.send_modal(
                await gen_modal(cog_module, cog.options, cog_instance)
            )


async def setup(bot):
    clear_cache()
    await bot.add_cog(ConfigCommands(bot), guild=bot.guilds[0])
