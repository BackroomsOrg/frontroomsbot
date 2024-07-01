import discord
from discord import app_commands
from discord.ext import tasks
import tempfile
from PIL import Image
import requests
import asyncio
import datetime

from bot import BackroomsBot
from ._config import ConfigCog, Cfg


TIME = datetime.time(hour=2, tzinfo=datetime.timezone.utc)


class AvatarEmojiCog(ConfigCog):
    server = Cfg(str)
    req_timeout = Cfg(int, default=30)

    def __init__(self, bot: BackroomsBot) -> None:
        super().__init__(bot)

        self.bot = bot
        self.lock = asyncio.Lock()
        self.context = ""

    @app_commands.command(
        name="force_avatars_reload",
        description="Force avatars emojis to be reloaded in pantry",
    )
    async def force_avatars_reload(self, interaction: discord.Interaction):
        await self.reload_avatars()

    @tasks.loop(time=TIME)
    async def reload_avatars(self):
        async with self.lock:
            await self.reload_avatars_impl()

    async def reload_avatars_impl(self):
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
            response = requests.get(avatar_url)
            with open(f"{tempdir}/{member_name}.png", "wb") as f:
                f.write(response.content)
            # resize the avatar
            image = Image.open(f"{tempdir}/{member_name}.png")
            image = image.resize((128, 128))
            image.save(f"{tempdir}/{member_name}.png")
            # upload the avatar as a new emoji to the pantry
            return await self.bot.pantry.create_custom_emoji(
                name=member_name, image=image
            )


async def setup(bot: BackroomsBot) -> None:
    await bot.add_cog(AvatarEmojiCog(bot), guild=bot.backrooms)
