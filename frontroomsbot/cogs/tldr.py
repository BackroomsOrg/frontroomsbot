import discord
from discord import (
    app_commands,
    MessageType,
    TextChannel,
    Message,
    Interaction,
    AppCommandType,
)
from discord.ext import commands
from bot import BackroomsBot
import google.generativeai as genai
import re
import json
from collections import defaultdict
from ._config import Cfg, ConfigCog

from consts import GEMINI_TOKEN


USER_RE = re.compile(r"<@\d+>")


class TldrError(Exception):
    def __init__(self, error_msg: str):
        self.error_msg = error_msg
        super().__init__(self.error_msg)


class TokensLimitExceededError(TldrError):
    pass


class MessageIdInvalidError(TldrError):
    pass


class StartMsgOlderThanEndMsgError(TldrError):
    def __init__(
        self,
        error_msg: str = "Starting message must not be newer than the ending message.",
    ):
        super().__init__(error_msg)


class TldrCog(ConfigCog):
    # TODO: make this configurable
    EPHEMERAL = True  # make the response ephemeral
    GEMINI_MODEL_NAME = Cfg(str, "gemini-1.5-flash")
    TOKEN_LIMIT = Cfg(int, 100_000)
    MESSAGES_LIMIT = Cfg(int, 10_000)

    def __init__(self, bot: BackroomsBot) -> None:
        super().__init__(bot)
        self.bot = bot
        genai.configure(api_key=GEMINI_TOKEN)
        # { (user_id, channel_id): [message_after, message_before] }
        self.boundaries: defaultdict[tuple[int, int], list[Message | None]] = (
            defaultdict(lambda: [None, None])
        )

        # Register the context menu commands
        self.ctx_menu_tldr_after = app_commands.ContextMenu(
            name="TL;DR After This",
            callback=self.ctx_menu_tldr_after_command,
            type=AppCommandType.message,  # only for messages
            guild_ids=[
                self.bot.backrooms.id
            ],  # lock the command to the backrooms guild
        )
        self.ctx_menu_tldr_before = app_commands.ContextMenu(
            name="TL;DR Before This",
            callback=self.ctx_menu_tldr_before_command,
            type=AppCommandType.message,  # only for messages
            guild_ids=[
                self.bot.backrooms.id
            ],  # lock the command to the backrooms guild
        )
        self.ctx_menu_tldr_this = app_commands.ContextMenu(
            name="TL;DR This One",
            callback=self.ctx_menu_tldr_this_command,
            type=AppCommandType.message,  # only for messages
            guild_ids=[
                self.bot.backrooms.id
            ],  # lock the command to the backrooms guild
        )
        self.bot.tree.add_command(self.ctx_menu_tldr_after)
        self.bot.tree.add_command(self.ctx_menu_tldr_before)
        self.bot.tree.add_command(self.ctx_menu_tldr_this)

    @app_commands.command(
        name="tldr",
        description="Vytvoří krátký souhrn mezi zprávami. Je nutné nastavit začátek.",
    )
    async def tldr(self, interaction: Interaction):
        """
        Command to generate a summary between two messages.
        The starting message must be set first.
        If the ending message is not set, the last message in the channel is used.
        """

        # defer response to avoid timeout
        await interaction.response.defer(ephemeral=self.EPHEMERAL)

        async def respond(content: str):
            """Helper function to send a followup response after defer to the interaction."""
            return await interaction.followup.send(
                content=content, ephemeral=self.EPHEMERAL
            )

        boundaries_key = (interaction.user.id, interaction.channel.id)
        message_after, message_before = self.boundaries.get(
            boundaries_key, [None, None]
        )
        if message_after is None:
            await respond("Please set the starting message first.")
            return
        if message_before is None:
            message_before = await self._get_last_message(interaction.channel)

        try:
            tldr = await self._tldr(interaction.channel, message_after, message_before)
            await respond(tldr)
        except TldrError as e:
            await respond(e.error_msg)
        except Exception as e:
            await respond("An unexpected error occurred.")
            raise e

    async def ctx_menu_tldr_after_command(
        self, interaction: Interaction, message_after: Message
    ):
        boundaries_key = (interaction.user.id, interaction.channel.id)
        self.boundaries[boundaries_key][0] = message_after
        await interaction.response.send_message(
            f"TL;DR after message set to {message_after.jump_url}", ephemeral=True
        )

    async def ctx_menu_tldr_before_command(
        self, interaction: Interaction, message_before: Message
    ):
        boundaries_key = (interaction.user.id, interaction.channel.id)
        self.boundaries[boundaries_key][1] = message_before
        await interaction.response.send_message(
            f"TL;DR before message set to {message_before.jump_url}", ephemeral=True
        )

    async def ctx_menu_tldr_this_command(
        self, interaction: Interaction, message: Message
    ):
        await interaction.response.defer(ephemeral=self.EPHEMERAL)
        tldr = await self._generate_tldr_from_single_message(message.content)
        await interaction.followup.send(tldr, ephemeral=self.EPHEMERAL)

    # Remove the commands from the tree when the cog is unloaded
    async def cog_unload(self) -> None:
        self.bot.tree.remove_command(self.ctx_menu_tldr_after)
        self.bot.tree.remove_command(self.ctx_menu_tldr_before)
        self.bot.tree.remove_command(self.ctx_menu_tldr_this)

    async def _get_last_message(self, channel: TextChannel) -> Message:
        # try to get the last message in the channel from cache
        message_before = channel.last_message
        if message_before is not None:
            return message_before
        # if not found, fetch the last message manually
        async for msg in channel.history(limit=1):
            return msg

    async def _generate_tldr_from_conversation(self, messages: str) -> str:
        model = genai.GenerativeModel(await self.GEMINI_MODEL_NAME)
        tokens = model.count_tokens(messages)
        if tokens.total_tokens > await self.TOKEN_LIMIT:
            raise TokensLimitExceededError(
                f"Input exceeds the token limit: {await self.TOKEN_LIMIT}, total tokens: {tokens.total_tokens}."
            )
        prompt = (
            "You are given a Discord conversation. Summarize the main points and key ideas "
            "in a concise manner in Czech. Focus on the most important information and provide "
            "a clear and coherent summary.\n\n"
            f"Conversation:\n{messages}"
        )
        return model.generate_content(prompt).text

    async def _generate_tldr_from_single_message(self, message: str) -> str:
        model = genai.GenerativeModel(await self.GEMINI_MODEL_NAME)
        tokens = model.count_tokens(message)
        if tokens.total_tokens > await self.TOKEN_LIMIT:
            raise TokensLimitExceededError(
                f"Input exceeds the token limit: {await self.TOKEN_LIMIT}, total tokens: {tokens.total_tokens}."
            )
        prompt = (
            "You are given a Discord message. Summarize the main points and key ideas "
            "in a concise manner in Czech. Focus on the most important information and provide "
            "a clear and coherent summary.\n\n"
            f"Message:\n{message}"
        )
        return model.generate_content(prompt).text

    async def _parse_message_id_to_message(
        self, channel: TextChannel, message_id: str
    ) -> Message:
        try:
            message_id = int(message_id)
        except ValueError:
            raise MessageIdInvalidError("Invalid message ID format.")
        try:
            message = await channel.fetch_message(message_id)
        except discord.NotFound:
            raise MessageIdInvalidError("Message not found based on the provided ID.")
        return message

    async def _tldr(
        self,
        channel: TextChannel,
        message_after: Message,
        message_before: Message,
    ) -> str:
        """
        Generate a TL;DR summary between two messages.

        :param channel: The channel where the messages are located
        :param message_after: The starting message
        :param message_before: The ending message
        :return: The generated TL;DR summary

        :raises TldrError: If an error occurs during the process

        """
        if message_after.created_at > message_before.created_at:
            raise StartMsgOlderThanEndMsgError()

        # Fetch the messages between the two messages and simplify them
        messages = []

        async for msg in channel.history(
            after=message_after,
            before=message_before,
            oldest_first=True,
            limit=await self.MESSAGES_LIMIT,
        ):
            if msg.author.bot:  # skip bot messages
                continue

            msg_content = msg.content

            # Replace user mentions with their names
            searches = USER_RE.findall(msg_content)
            for search in searches:
                user_id = search[2:-1]
                user = await self.bot.fetch_user(user_id)
                msg_content = msg_content.replace(search, user.name)

            simplified_message = {
                "id": msg.id,
                "author": msg.author.name,
                "created_at": msg.created_at.strftime("%Y-%m-%d %H:%M:%S"),
                "message": msg_content,
            }
            if msg.type == MessageType.reply:
                simplified_message["reply_to"] = msg.reference.message_id
            messages.append(simplified_message)

        serialized = json.dumps(messages)
        tldr = await self._generate_tldr_from_conversation(serialized)
        return tldr


async def setup(bot: BackroomsBot) -> None:
    await bot.add_cog(TldrCog(bot), guild=bot.backrooms)
