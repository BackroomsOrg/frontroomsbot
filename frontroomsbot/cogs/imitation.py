import discord
from discord import app_commands
import httpx
import re
import asyncio

from bot import BackroomsBot
from ._config import ConfigCog, Cfg
from discord import Interaction

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

    async def user_autocomplete(self, interaction: Interaction, current: str):
        authors = [
            "kubikon",
            "theramsay",
            "metjuas",
            "logw",
            "throwdemgunz",
            "s1r_o",
            "gzvv",
            "ithislen",
            "_.spoot._",
            "roytak",
            "tominoftw",
            ".stepha",
            "jurge_chorche",
            "ericc727",
            "Backrooms bot",
            "andrejmokris",
            "noname7571",
            "frogerius",
            "kulvplote",
            "soromis",
            "krekon_",
            "lakmatiol",
            "josefkuchar",
            "mrstinky",
            "louda7658",
            "tamoka.",
            "dajvid",
            "kocotom",
            "kubosh",
            "upwell",
            "padi142",
            "prity_joke",
            "jankaxdd",
            "tokugawa6139",
            "toaster",
            "oty_suvenyr",
            "Rubbergod",
            "GrillBot",
            "jezko",
            ".jerrys",
            "redak",
            "donmegonasayit",
            "fpmk",
            "whoislisalisa",
            "Dank Memer",
            "nevarilovav",
            "OpenBB Bot",
            "avepanda",
            "bonobonobono",
            "man1ak",
            "t1mea_",
            "nycella",
            "headclass",
            "puroki",
            "_blaza_",
            "natyhr",
            "Dyno",
            "Jockie Music (2)",
            "louda",
            "Tokugawa",
            "cultsauce_",
            "Agent Smith",
            "Vlčice",
            "Compiler",
            "Cappuccino",
            "solumath",
        ]
        authors = [app_commands.Choice(name=a, value=a) for a in authors]
        if not current:
            return authors

        return [a for a in authors if a.name.startswith(current.lower())]

    def get_emoji(self, name: str):
        """Get the emoji by name"""

        for emoji in self.bot.emojis:
            if emoji.name.lower() == name.lower():
                return emoji
        return f":{name}:"

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
        backrooms = self.bot.get_guild(self.bot.backrooms.id)
        pantry = self.bot.get_guild(self.bot.pantry_id)

        emoji = "❄️"  # Default emoji
        member = backrooms.get_member_named(author)
        if member:
            for em in pantry.emojis:
                if em.name == str(member.id):
                    emoji = em
                    break

        # Patch emojis
        content = re.sub(r":(\w+):", lambda x: str(self.get_emoji(x.group(1))), content)

        message = f"{emoji}  **{author}** | *msg ID: [{id}]*"
        if reply_id:
            message += f" | *Reply to: [{reply_id}]*"
        message += f"\n>>> {content}"
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
                    header = START_HEADER_ID
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
    @app_commands.autocomplete(author=user_autocomplete)
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
                header = START_HEADER_ID

                if author:
                    header += (
                        await self.get_prediction(header, MESSAGE_ID)
                        + MESSAGE_ID
                        + author
                        + REPLY_ID
                    )
                else:
                    header += await self.get_prediction(header, REPLY_ID) + REPLY_ID

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
    async def clear_context(self, interaction: discord.Interaction):
        """Clear the imitation context"""

        if not self.lock.locked():
            async with self.lock:
                self.context = ""

                await interaction.response.send_message("*Kontext byl smazán*")
        else:
            await self.send_busy_message(interaction)


async def setup(bot: BackroomsBot) -> None:
    await bot.add_cog(ImitationCog(bot), guild=bot.backrooms)
