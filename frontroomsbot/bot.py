import os
import discord
from traceback import print_exc
from io import StringIO
import httpx

from discord.ext import commands
import motor.motor_asyncio as ma

from consts import TOKEN, GUILD, DB_CONN, COGS_DIR, ERROR_WH, PANTRY_GUILD

intents = discord.Intents.default()
intents.message_content = True
intents.reactions = True

# simple object only with id attribute used on cogs setup
backrooms = discord.Object(id=GUILD)


class BackroomsBot(commands.Bot):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        db_client = ma.AsyncIOMotorClient(DB_CONN)
        self.db = db_client.bot_database
        self.backrooms = backrooms
        self.pantry_id = int(PANTRY_GUILD)

    async def setup_hook(self):
        # loads all cogs
        for filename in os.listdir(COGS_DIR):
            if filename.endswith("py") and not filename.startswith("_"):
                await self.load_extension(
                    f"{'.'.join(COGS_DIR.split('/'))}.{filename[:-3]}"
                )

        # syncs the command tree with the backrooms guild
        await self.tree.sync(guild=self.backrooms)

    async def on_error(self, event: str, *args, **kwargs):
        content = StringIO()
        print_exc(file=content)
        print(content.getvalue())
        data = {
            "content": f"Bot ran into an error in event {event!r} with \n`{args=!r}`\n`{kwargs=!r}`",
            "allowed_mentions": {"parse": []},
            "embeds": [
                {
                    "title": "Traceback",
                    "description": "```" + content.getvalue()[-3950:] + "```",
                }
            ],
        }
        async with httpx.AsyncClient() as cl:
            # use a webhook instead of the discord connection in
            # case the error is caused by being disconnected from discord
            # also prevents error reporting from breaking API limits
            await cl.post(ERROR_WH, json=data)


client = BackroomsBot(command_prefix="!", intents=intents)

if __name__ == "__main__":
    client.run(TOKEN)
