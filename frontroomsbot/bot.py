import os
import discord
import toml

from discord.ext import commands
import motor.motor_asyncio as ma

from consts import TOKEN, GUILD, DB_CONN, COGS_DIR

intents = discord.Intents.default()
intents.message_content = True
intents.reactions = True

guild = discord.Object(id=GUILD)


class BackroomsBot(commands.Bot):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        db_client = ma.AsyncIOMotorClient(DB_CONN)
        self.db = db_client.bot_database
        with open("config.toml", "r") as f:
            self.config = toml.load(f)

    async def on_ready(self):
        for filename in os.listdir(COGS_DIR):
            if filename.endswith("py") and not filename.startswith("_"):
                await self.load_extension(
                    f"{'.'.join(COGS_DIR.split('/'))}.{filename[:-3]}"
                )

        print(f"{self.user} has connected to Discord!")


client = BackroomsBot(command_prefix="!", intents=intents)

if __name__ == "__main__":
    client.run(TOKEN)