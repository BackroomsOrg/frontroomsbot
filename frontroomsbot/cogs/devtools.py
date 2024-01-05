from bot import BackroomsBot
from discord.ext import commands
from consts import ERROR_WH
import httpx
from pathlib import Path
import time

# strip filename, leave cogs/, then frontroomsbot/
DOT_GIT = Path(__file__).parent.parent.parent / ".git"


class DevTools(commands.Cog):
    def __init__(self, bot: BackroomsBot) -> None:
        self.bot = bot

    def doctor(self):
        """
        Run various self-checks to find common problems with the bot deployment
        """
        guilds = list(self.bot.guilds)
        assert (
            guilds[0].id == self.bot.backrooms.id
        ), f"The configured GUILD_ID is not the guild the bot is in, {self.bot.backrooms.id} vs {guilds[0].id}"
        assert len(guilds) == 1, "The bot is in multiple guilds"

        bad_commands = []
        for cmd in self.bot.tree.walk_commands():
            if not cmd.guild_only:
                bad_commands.append(cmd)
        if bad_commands:
            raise RuntimeError(
                f"Found commands that aren't guild only: {bad_commands}, these will not sync via /sync"
            )
        print("self check ok")

    @commands.Cog.listener()
    async def on_ready(self):
        print("bot ready, running self check")
        self.doctor()
        try:
            git_revision = (DOT_GIT / "refs/heads/master").read_text()
        except IOError:
            git_revision = "git revision not found"
        data = {
            "content": f"{self.bot.user} is up at <t:{int(time.time())}:T> using git: `{git_revision.strip()}`.",
            "allowed_mentions": {"parse": []},
        }
        async with httpx.AsyncClient() as cl:
            await cl.post(ERROR_WH, json=data)


async def setup(bot):
    await bot.add_cog(DevTools(bot), guild=bot.backrooms)
