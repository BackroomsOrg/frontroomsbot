import discord
from discord import app_commands, MessageType
from bot import BackroomsBot
from ._config import ConfigCog
import google.generativeai as genai
import re

from consts import GEMINI_TOKEN

USER_RE = re.compile(r"<@\d+>")


class TldrCog(ConfigCog):

    def __init__(self, bot: BackroomsBot) -> None:
        super().__init__(bot)
        genai.configure(api_key=GEMINI_TOKEN)
        self.model = genai.GenerativeModel("gemini-1.5-flash")
        self.token_limit = 1000000

    @app_commands.command(
        name="tldr", description="Vytvoří krátký souhrn mezi zprávami"
    )
    async def tldr(
        self,
        interaction: discord.Interaction,
        message_id_start: int,
        message_id_end: int | None = None,
    ):
        # defer response to avoid timeout
        await interaction.response.defer()

        # Get the channel
        channel = interaction.channel

        # Fetch the starting and ending messages
        message_start = await channel.fetch_message(message_id_start)
        # Fetch the ending message or use the last message in the channel if not provided
        if message_id_end is None:
            # Fetch the ending message or use the last message in the channel if not provided
            if message_id_end is None:
                message_end = None
                async for msg in channel.history(limit=1):
                    message_end = msg
                    break
        else:
            message_end = await channel.fetch_message(message_id_end)

        if message_start is None:
            await interaction.followup.send(content="Starting message not found.")
            return
        if message_end is None:
            await interaction.followup.send(content="Ending message not found.")
            return

        # Ensure the message_id_start is older than message_id_end
        if message_start.created_at >= message_end.created_at:
            await interaction.followup.send(
                content="Starting message must be older than the ending message."
            )
            return

        # Fetch the messages between the two message IDs
        messages = []
        async for msg in channel.history(
            after=message_start, before=message_end, oldest_first=True
        ):
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

        # Convert the messages to JSON format
        input = str(messages)

        # Generate a TLDR summary
        tokens = self.model.count_tokens(input)
        if tokens.total_tokens > self.token_limit:
            await interaction.followup.send(
                content=f"Input exceeds the token limit: {self.token_limit}, total tokens: {tokens.total_tokens}."
            )
            return
        prompt = (
            "You are given a Discord conversation. Summarize the main points and key ideas "
            "in a concise manner in Czech. Focus on the most important information and provide "
            "a clear and coherent summary.\n\n"
            f"Conversation:\n{input}"
        )
        response = self.model.generate_content(prompt)

        await interaction.followup.send(content=response.text)


async def setup(bot: BackroomsBot) -> None:
    await bot.add_cog(TldrCog(bot), guild=bot.backrooms)
