import discord
from discord import app_commands
import httpx
import re
from random import randrange
import asyncio

from bot import BackroomsBot
from ._config import ConfigCog, Cfg

START_HEADER_ID = "<|start_header_id|>"
END_HEADER_ID = "<|end_header_id|>"
MESSAGE_ID = "<|reserved_special_token_0|>"
REPLY_ID = "<|reserved_special_token_1|>"
END_MESSAGE_ID = "<|reserved_special_token_4|>"


class InvalidResponseException(Exception):
    """The response from the model was invalid"""

    pass


class ImitationCog(ConfigCog):
    server = Cfg(str)
    req_timeout = Cfg(int, default=30)

    def __init__(self, bot: BackroomsBot) -> None:
        super().__init__(bot)

        self.bot = bot
        self.lock = asyncio.Lock()
        self.context = ""
        self.id = self.generate_id()

    def get_formatted_message(
        self, author: str, content: str, id: int, reply_id: int = None
    ):
        """
        Format the message to be sent

        :param author: The author of the message
        :param content: The content of the message
        :param id: The ID of the message
        :param reply_id: The ID of the message being replied to
        :return: The formatted message
        """

        message = f"**{author}** *ID: [{id}]"
        if reply_id:
            message += f" | Reply to: [{reply_id}]"
        message += f"*\n>>> {content}"
        return message

    def get_message_from_raw(self, raw: str):
        """
        Get the message from the raw model response

        :param raw: The raw model response
        :return: The formatted message
        """

        match = re.match(
            r"<\|start_header_id\|>(\d+)<\|reserved_special_token_0\|>(.*)<\|reserved_special_token_1\|>(\d*)<\|end_header_id\|>\n([\S\n\t\v ]+)<\|reserved_special_token_4\|>\n\n",
            raw,
        )
        if not match:
            raise InvalidResponseException()

        author = match.group(2).strip()
        content = match.group(4).strip()
        id = match.group(1).strip()
        reply_id = match.group(3).strip()

        return self.get_formatted_message(author, content, id, reply_id)

    def generate_id(self):
        """Generate fake discord message ID"""

        # 18 - 19 digits
        return randrange(10**17, 10**19)

    def get_id(self):
        """Increment the fake discord message ID by reasonable amount and return it"""

        # Increment by some random relatively small number
        self.id += randrange(10, 500)
        return self.id

    async def respond(self, interaction: discord.Interaction, raw: str, first=True):
        """
        Respond to the interaction

        :param interaction: The interaction to respond to
        :param raw: The raw model response
        :param first: Whether this is the first message in the conversation
        """

        print(raw)
        try:
            message = self.get_message_from_raw(raw)
            self.context += raw
        except InvalidResponseException:
            message = "*Nepodařilo se získat odpověď od modelu*"
        if first:
            await interaction.followup.send(message)
        else:
            await interaction.channel.send(message)

    async def send_busy_message(self, interaction: discord.Interaction):
        """Send a message that the bot is busy"""

        await interaction.response.send_message(
            "*Momentálně je vykonávána jiná akce, prosím čekejte*", ephemeral=True
        )

    async def get_prediction(self, prompt: str, stop: str = START_HEADER_ID):
        """
        Get the prediction from the model
        Context is included

        :param prompt: The prompt to send to the model
        :param stop: The stop token to stop the model at
        :return: The model response
        """

        data = {
            "prompt": self.context + prompt,
            "stop": [stop],
            "cache_prompt": True,  # Existing context won't have to be evaluated again
        }

        async with httpx.AsyncClient() as ac:
            response = await ac.post(
                f"{await self.server}/completion",
                json=data,
                timeout=await self.req_timeout,
            )
        json = response.json()

        if response.status_code != 200:
            raise RuntimeError(f"Model failed {response.status_code}: {json}")

        return json["content"]

    @app_commands.command(
        name="imitation_continue", description="Volné pokračování kontextu"
    )
    async def continue_context(
        self, interaction: discord.Interaction, message_count: int = 1
    ):
        """
        Continue context with the model

        :param message_count: The number of messages to generate
        """

        if message_count < 1 or message_count > 10:
            await interaction.response.send_message(
                "*Počet zpráv musí být v rozmezí 1 až 10*", ephemeral=True
            )
            return

        if not self.lock.locked():
            async with self.lock:
                await interaction.response.defer()
                for i, _ in enumerate(range(message_count)):
                    # Build the header
                    header = START_HEADER_ID + str(self.get_id()) + MESSAGE_ID
                    # Get continuation from the model
                    prediction = await self.get_prediction(header)
                    # Include header, because model only returns new tokens
                    content = header + prediction
                    await self.respond(interaction, content, i == 0)
        else:
            await self.send_busy_message(interaction)

    @app_commands.command(
        name="imitation_insert",
        description="Vložení zprávy do kontextu",
    )
    async def insert_context(
        self,
        interaction: discord.Interaction,
        author: str = None,
        content: str = None,
        continue_content: bool = False,
        reply_id: str = None,
    ):
        """
        Insert a message into the imitation context

        :param author: The author of the message
        :param content: The content of the message
        :param continue_content: Whether to continue the content
        :param reply_id: The ID of the message being replied to
        """

        if not self.lock.locked():
            async with self.lock:
                await interaction.response.defer()

                # Build the header
                header = START_HEADER_ID + str(self.get_id()) + MESSAGE_ID

                # If author is not provided, get it from the model
                if not author:
                    author = await self.get_prediction(header, REPLY_ID)
                header += author + REPLY_ID

                # Only include reply ID if it is provided
                if reply_id:
                    header += reply_id
                header += END_HEADER_ID + "\n"

                # If content is not provided, get it from the model
                if not content:
                    prediction = await self.get_prediction(header)
                    content = header + prediction
                # Continue the content if specified
                elif content and continue_content:
                    content = header + content
                    prediction = await self.get_prediction(content)
                    content += prediction
                # Otherwise, just include the content with correct footer
                else:
                    content = header + content + END_MESSAGE_ID + "\n\n"
                await self.respond(interaction, content)
        else:
            await self.send_busy_message(interaction)

    @app_commands.command(name="imitation_clear", description="Smazání kontextu")
    async def clear_context(
        self, interaction: discord.Interaction, starting_id: int = None
    ):
        """Clear the imitation context"""

        if not self.lock.locked():
            async with self.lock:
                self.context = ""

                if not starting_id:
                    self.id = self.generate_id()
                else:
                    self.id = starting_id

                await interaction.response.send_message("*Kontext byl smazán*")
        else:
            await self.send_busy_message(interaction)


async def setup(bot: BackroomsBot) -> None:
    await bot.add_cog(ImitationCog(bot), guild=bot.backrooms)
