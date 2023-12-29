import datetime
import discord
from discord.ext import commands

from bot import BackroomsBot
from .utils.bookmarks import Bookmark, BookmarkView


class ReactionUtilsCog(commands.Cog):
    def __init__(self, bot: BackroomsBot) -> None:
        self.bot = bot

    @commands.Cog.listener()
    async def on_raw_reaction_add(self, payload: discord.RawReactionActionEvent):
        reaction = payload.emoji.name
        channel = self.bot.get_channel(payload.channel_id)
        message = await channel.fetch_message(payload.message_id)

        user = await self.bot.fetch_user(payload.user_id)

        match reaction:
            case "🔖":
                direct = await user.create_dm()
                if channel == direct:
                    return

                bookmark = Bookmark(message.author, message, direct)
                await bookmark.add_media()
                await bookmark.send()

            case "📌":
                await self.pin_handle(message, channel)
            case "🔇":
                await self.timeout_handle(message)
            case _:
                return

    async def pin_handle(
        self, message: discord.message.Message, channel: discord.channel.TextChannel
    ):
        """Handles auto pinning of messages

        :param message: Message that received a reaction
        :param channel: Channel where the message is
        :return:
        """
        for react in message.reactions:
            if (
                react.emoji == "📌"
                and not message.pinned
                and not message.is_system()
                and react.count >= self.bot.config["reactions"]["pin_count"]
            ):
                # FIXME
                # pins = await channel.pins()
                # we need to maintain when was the last warning about filled pins,
                # otherwise we will get spammed by the pins full message
                await message.pin()
                break

    async def timeout_handle(self, message: discord.message.Message):
        """Handles auto timeout of users

        :param message: Message that received a reaction
        :return
        """
        for react in message.reactions:
            if (
                react.emoji == "🔇"
                and not message.author.is_timed_out()
                and not message.is_system()
                and react.count >= self.bot.config["reactions"]["timeout_count"]
            ):
                # FIXME
                # we need to maintain when was the last timeout,
                # otherwise someone could get locked out
                duration = datetime.timedelta(
                    minutes=self.bot.config["reactions"]["timeout_duration"]
                )
                await message.author.timeout(duration)
                break


async def setup(bot: BackroomsBot) -> None:
    bot.add_view(BookmarkView())
    await bot.add_cog(ReactionUtilsCog(bot), guild=bot.guilds[0])