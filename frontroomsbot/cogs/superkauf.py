from discord.ext import commands
import websockets
from discord import Embed, Colour
import json
from ._config import ConfigCog, Cfg
import asyncio


from bot import BackroomsBot


class WebSocketClient:
    def __init__(self, bot, websocket_url):
        self.bot = bot
        self.websocket_url = websocket_url

    async def connect(self, channel_id):
        reconnect_timeout = 1
        while True:
            try:
                async with websockets.connect(self.websocket_url) as ws:
                    while True:
                        reconnect_timeout = 1
                        parsedMessage = json.loads(await ws.recv())
                        user_data = parsedMessage["user"]
                        post_data = parsedMessage["post"]
                        store_data = parsedMessage["store"]

                        channel = self.bot.get_channel(channel_id)

                        embed = Embed(
                            description=post_data["description"],
                            colour=Colour.from_rgb(113, 93, 242),
                        )
                        embed.add_field(
                            name="Price",
                            value=str(post_data["price"]) + "Kč",
                            inline=True,
                        )
                        embed.add_field(
                            name="Store", value=str(store_data["name"]), inline=True
                        )
                        embed.set_author(
                            name="SuperKauf",
                            icon_url="https://storage.googleapis.com/superkauf/logos/logo1.png",
                            url="https://superkauf.krejzac.cz",
                        )
                        embed.set_image(url=post_data["image"])
                        embed.set_footer(
                            text=user_data["username"],
                            icon_url=user_data["profile_picture"],
                        )

                        await channel.send(embed=embed)

            except websockets.ConnectionClosed:
                reconnect_timeout *= 2
                print(
                    f"Connection closed. Reconnecting in {reconnect_timeout} seconds."
                )
                await asyncio.sleep(reconnect_timeout)


class SuperkaufCog(ConfigCog):
    superkaufroom_id = Cfg(int)

    def __init__(self, bot: BackroomsBot) -> None:
        super().__init__(bot)
        self.bot = bot
        websocket_url = "wss://superkauf-updates.krejzac.cz"

        self.websocket_client = WebSocketClient(bot, websocket_url)
        self.ready = False
        self.task = None

    async def connect(self):
        self.task = self.bot.loop.create_task(
            self.websocket_client.connect(await self.superkaufroom_id)
        )

    @commands.Cog.listener()
    async def on_ready(self):
        self.ready = True
        if not self.task:
            await self.connect()

    async def cog_load(self):
        if self.ready and not self.task:
            await self.connect()

    async def cog_unload(self) -> None:
        if self.task and self.task.cancel():
            try:
                await self.task
            except asyncio.CancelledError:
                pass
        self.task = None


async def setup(bot: BackroomsBot) -> None:
    await bot.add_cog(SuperkaufCog(bot), guild=bot.backrooms)
