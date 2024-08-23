from bot import BackroomsBot
from discord import app_commands
import discord
from ._config import ConfigCog


class PinSquashCog(ConfigCog):
    def __init__(self, bot: BackroomsBot) -> None:
        super().__init__(bot)

    @app_commands.command(name="pin_squash", description="Squashes pins")
    async def pin_squash(self, interaction: discord.Interaction):
        channel = interaction.channel
        pins = await channel.pins()

        # Create a list to store links to pinned messages
        pin_links = []

        # Unpin all messages and collect their links
        for pin in pins:
            await pin.unpin()
            pin_links.append(f"[Message]({pin.jump_url})")

        if pin_links:
            chunks = []
            current_chunk = "Previously pinned messages:\n"

            for link in pin_links:
                if len(current_chunk) + len(link) + 1 > 2000:
                    chunks.append(current_chunk)
                    current_chunk = link + "\n"
                else:
                    current_chunk += link + "\n"

            if current_chunk:
                chunks.append(current_chunk)

        for i, chunk in enumerate(chunks):
            new_pin = await channel.send(chunk)
            if i == 0:
                await new_pin.pin()
        else:
            await interaction.response.send_message("No pins found to squash.")


async def setup(bot: BackroomsBot) -> None:
    await bot.add_cog(PinSquashCog(bot), guild=bot.backrooms)
