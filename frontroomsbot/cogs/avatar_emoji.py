import discord
from discord import app_commands
import tempfile
from PIL import Image
import httpx

from bot import BackroomsBot
from ._config import ConfigCog, Cfg


class AvatarEmojiCog(ConfigCog):
    backrooms_channel_id = Cfg(int)

    def __init__(self, bot: BackroomsBot) -> None:
        super().__init__(bot)

        self.bot = bot

    @app_commands.command(
        name="reload_avatars",
        description="Force avatars emojis to be reloaded in pantry",
    )
    async def reload_avatars(self, interaction: discord.Interaction):
        # create an emoji for each member in the backrooms channel
        backrooms_channel = self.bot.get_channel(await self.backrooms_channel_id)
        for member in backrooms_channel.members:
            await self.create_avatar_emoji_in_pantry(
                member.id, member.display_avatar.url
            )
        await interaction.response.send_message("Avatars reloaded", ephemeral=True)

    async def create_avatar_emoji_in_pantry(
        self, member_id: int, avatar_url: str
    ) -> discord.Emoji:
        # delete the emoji if it already exists
        pantry = self.bot.get_guild(self.bot.pantry_id)
        for em in pantry.emojis:
            if em.name == str(member_id):
                await em.delete()

        with tempfile.TemporaryDirectory() as tempdir:
            # download the avatar
            async with httpx.AsyncClient() as client:
                response = await client.get(avatar_url, timeout=10)
            image_path = f"{tempdir}/{member_id}.png"
            with open(image_path, "wb") as f:
                f.write(response.content)
            # resize the avatar
            image = Image.open(image_path)
            image = image.resize((128, 128))
            image.save(image_path)
            # upload the avatar as a new emoji to the pantry
            return await pantry.create_custom_emoji(
                name=member_id, image=open(image_path, "rb").read()
            )


async def setup(bot: BackroomsBot) -> None:
    await bot.add_cog(AvatarEmojiCog(bot), guild=bot.backrooms)
