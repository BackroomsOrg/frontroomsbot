import discord
from discord import app_commands
from discord.ext import tasks
import tempfile
from PIL import Image
import httpx

from bot import BackroomsBot
from ._config import ConfigCog, Cfg


class AvatarEmojiCog(ConfigCog):
    def __init__(self, bot: BackroomsBot) -> None:
        super().__init__(bot)

        self.bot = bot

    @app_commands.command(
        name="reload_avatars",
        description="Force avatars emojis to be reloaded in pantry",
    )
    @tasks.loop(hours=4 * 24)
    async def reload_avatars(self):
        # create an emoji for each member in the backrooms
        for member in self.bot.backrooms.members:
            await self.create_avatar_emoji_in_pantry(member.name, member.avatar_url)

    async def create_avatar_emoji_in_pantry(
        self, member_name: str, avatar_url: str
    ) -> discord.Emoji:
        # delete the emoji if it already exists
        for em in self.bot.pantry.emojis:
            if em.name == member_name:
                await em.delete()

        with tempfile.TemporaryDirectory() as tempdir:
            # download the avatar
            async with httpx.AsyncClient() as client:
                response = await client.get(avatar_url, timeout=30)
            image_path = f"{tempdir}/{member_name}.png"
            with open(image_path, "wb") as f:
                f.write(response.content)
            # resize the avatar
            image = Image.open(image_path)
            image = image.resize((128, 128))
            image.save(image_path)
            # upload the avatar as a new emoji to the pantry
            return await self.bot.pantry.create_custom_emoji(
                name=member_name, image=open(image_path, "rb").read()
            )


async def setup(bot: BackroomsBot) -> None:
    await bot.add_cog(AvatarEmojiCog(bot), guild=bot.backrooms)
