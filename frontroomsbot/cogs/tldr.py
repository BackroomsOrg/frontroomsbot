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


class TldrCog(commands.Cog):
    EPHEMERAL = True  # make the response ephemeral
    GEMINI_MODEL_NAME = "gemini-1.5-flash"
    TOKEN_LIMIT = 100_000  # to be fine-tuned
    MESSAGES_LIMIT = 10_000  # to be fine-tuned

    def __init__(self, bot: BackroomsBot) -> None:
        self.bot = bot
        genai.configure(api_key=GEMINI_TOKEN)
        self.model = genai.GenerativeModel(self.GEMINI_MODEL_NAME)
        self.boundaries = {}
        self.ctx_menu_tldr_start = app_commands.ContextMenu(
            name="TL;DR Start",
            callback=self.ctx_menu_tldr_start,
            type=AppCommandType.message,
            guild_ids=[
                self.bot.backrooms.id
            ],  # needed to lock the command to the backrooms guild
        )
        self.ctx_menu_tldr_end = app_commands.ContextMenu(
            name="TL;DR End",
            callback=self.ctx_menu_tldr_end,
            type=AppCommandType.message,
            guild_ids=[
                self.bot.backrooms.id
            ],  # needed to lock the command to the backrooms guild
        )
        self.ctx_menu_tldr_execute = app_commands.ContextMenu(
            name="TL;DR Execute",
            callback=self.ctx_menu_tldr_execute,
            type=AppCommandType.message,
            guild_ids=[
                self.bot.backrooms.id
            ],  # needed to lock the command to the backrooms guild
        )
        self.bot.tree.add_command(self.ctx_menu_tldr_start)
        self.bot.tree.add_command(self.ctx_menu_tldr_end)
        self.bot.tree.add_command(self.ctx_menu_tldr_execute)

    @app_commands.command(
        name="tldr", description="Vytvoří krátký souhrn mezi zprávami"
    )
    async def tldr(
        self,
        interaction: Interaction,
        message_id_start: str,
        message_id_end: str | None = None,
    ):
        channel = interaction.channel

        try:
            message_start = await self._parse_message_id_to_message(
                channel, message_id_start
            )
            if message_id_end is not None:
                message_end = await self._parse_message_id_to_message(
                    channel, message_id_end
                )
            else:
                message_end = await self._get_last_message(channel)
        except TldrError as e:
            await interaction.response.send_message(
                content=e.error_msg, ephemeral=self.EPHEMERAL
            )
            return
        except Exception as e:
            await interaction.response.send_message(
                content="An unexpected error occurred.", ephemeral=self.EPHEMERAL
            )
            raise e

        await self._tldr(interaction, message_start, message_end)

    async def ctx_menu_tldr_start(
        self, interaction: Interaction, message_start: Message
    ):
        # TODO
        channel = interaction.channel
        try:
            message_end = await self._get_last_message(channel)
        except TldrError as e:
            await interaction.response.send_message(
                content=e.error_msg, ephemeral=self.EPHEMERAL
            )
            return
        await self._tldr(interaction, message_start, message_end)

    async def ctx_menu_tldr_end(self, interaction: Interaction, message_start: Message):
        # TODO
        channel = interaction.channel
        try:
            message_end = await self._get_last_message(channel)
        except TldrError as e:
            await interaction.response.send_message(
                content=e.error_msg, ephemeral=self.EPHEMERAL
            )
            return
        await self._tldr(interaction, message_start, message_end)

    async def ctx_menu_tldr_start_execute(
        self, interaction: Interaction, message_start: Message
    ):
        # TODO
        channel = interaction.channel
        try:
            message_end = await self._get_last_message(channel)
        except TldrError as e:
            await interaction.response.send_message(
                content=e.error_msg, ephemeral=self.EPHEMERAL
            )
            return
        await self._tldr(interaction, message_start, message_end)

    # Remove the commands from the tree when the cog is unloaded
    async def cog_unload(self) -> None:
        self.bot.tree.remove_command(
            self.ctx_menu_tldr_start.name, type=self.ctx_menu_tldr_start.type
        )
        self.bot.tree.remove_command(
            self.ctx_menu_tldr_end.name, type=self.ctx_menu_tldr_end.type
        )
        self.bot.tree.remove_command(
            self.ctx_menu_tldr_execute.name, type=self.ctx_menu_tldr_execute.type
        )

    async def _get_last_message(self, channel: TextChannel) -> Message:
        # try to get the last message in the channel from cache
        message_end = channel.last_message
        if message_end is not None:
            return message_end
        # if not found, fetch the last message manually
        async for msg in channel.history(limit=1):
            return msg

    def _generate_tldr(self, messages: str) -> str:
        tokens = self.model.count_tokens(messages)
        if tokens.total_tokens > self.TOKEN_LIMIT:
            raise TokensLimitExceededError(
                f"Input exceeds the token limit: {self.TOKEN_LIMIT}, total tokens: {tokens.total_tokens}."
            )
        prompt = (
            "You are given a Discord conversation. Summarize the main points and key ideas "
            "in a concise manner in Czech. Focus on the most important information and provide "
            "a clear and coherent summary.\n\n"
            f"Conversation:\n{messages}"
        )
        return self.model.generate_content(prompt).text

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
        interaction: discord.Interaction,
        message_start: Message,
        message_end: Message,
    ):
        try:
            # defer response to avoid timeout
            await interaction.response.defer(ephemeral=self.EPHEMERAL)

            channel = interaction.channel

            if message_start.created_at > message_end.created_at:
                raise StartMsgOlderThanEndMsgError()

            # Fetch the messages between the two messages and simplify them
            messages = []

            async for msg in channel.history(
                after=message_start,
                before=message_end,
                oldest_first=True,
                limit=self.MESSAGES_LIMIT,
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
            print("serialized: ", serialized)
            tldr = self._generate_tldr(serialized)
            print("tldr: ", tldr)
            await interaction.followup.send(content=tldr, ephemeral=self.EPHEMERAL)

        except TldrError as e:
            await interaction.followup.send(
                content=e.error_msg, ephemeral=self.EPHEMERAL
            )
        except Exception as e:
            await interaction.followup.send(
                content="An unexpected error occurred.", ephemeral=self.EPHEMERAL
            )
            raise e


async def setup(bot: BackroomsBot) -> None:
    await bot.add_cog(TldrCog(bot), guild=bot.backrooms)
