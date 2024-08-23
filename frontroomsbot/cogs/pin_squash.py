from bot import BackroomsBot
from discord import app_commands
import discord
from ._config import ConfigCog

class PinSquashCog(ConfigCog):
    def __init__(self, bot: BackroomsBot) -> None:
        super().__init__(bot)
    
    @app_commands.command(name="pin_squash", description="Squashes pins")
    async def pin_squash(
        self, interaction: discord.Interaction
    ):
        channel = interaction.channel
        pins = await channel.pins()
        
        # Create a list to store links to pinned messages
        pin_links = []
        
        # Unpin all messages and collect their links
        for pin in pins:
            await pin.unpin()
            pin_links.append(f"[Message]({pin.jump_url})")

        if pin_links:
            content = "Previously pinned messages:\n" + "\n".join(pin_links)
            new_pin = await channel.send(content)
            await new_pin.pin()
            
            await interaction.response.send_message("Pins squashed and new summary pinned.")
        else:
            await interaction.response.send_message("No pins found to squash.")

async def setup(bot: BackroomsBot) -> None:
    await bot.add_cog(PinSquashCog(bot), guild=bot.backrooms)
