from discord.ext import commands
import websockets
from discord import Embed, Colour
import json


from bot import BackroomsBot

class WebSocketClient:
    def __init__(self, bot, websocket_url):
        self.bot = bot
        self.websocket_url = websocket_url

    async def connect(self):
        async with websockets.connect(self.websocket_url) as ws:
            while True:
                message = await ws.recv()
                parsedMessage = json.loads(message)
                
                channel = self.bot.get_channel(1193344830382813254)
                embed = Embed(title="New post!", description=parsedMessage["description"], colour=Colour.blue())
                embed.add_field(name="Price:", value=str(parsedMessage["price"]) + "Kč", inline=False)
                embed.add_field(name="StoreId:", value=str(parsedMessage["store"]), inline=False)
                embed.set_image(url = parsedMessage["image"])
                embed.set_footer(text="Powered by TurboDeal", icon_url="https://wwrhodyufftnwdbafguo.supabase.co/storage/v1/object/public/profile_pics/kauf_logo.png")

                await channel.send(embed=embed)


class SuperkaufCog(commands.Cog):
    def __init__(self, bot: BackroomsBot) -> None:
        self.bot = bot
        websocket_url = "wss://superkauf-updates.krejzac.cz"
        self.websocket_url = websocket_url
        self.websocket_client = WebSocketClient(bot, websocket_url)

    @commands.Cog.listener()
    async def on_ready(self):
        self.bot.loop.create_task(self.websocket_client.connect())


async def setup(bot: BackroomsBot) -> None:
    await bot.add_cog(SuperkaufCog(bot), guild=bot.backrooms)