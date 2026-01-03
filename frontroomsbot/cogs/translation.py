import discord
from discord.ext import commands
from discord import app_commands
import google.generativeai as genai

from bot import BackroomsBot
from consts import GEMINI_TOKEN


class TranslationCog(commands.Cog):
    def __init__(self, bot: BackroomsBot) -> None:
        self.bot = bot
        genai.configure(api_key=GEMINI_TOKEN)

    @app_commands.command(
        name="translate", description="Translate the last n messages to English"
    )
    @app_commands.describe(n="Number of messages to translate (default: 10)")
    async def translate(self, interaction: discord.Interaction, n: int = 10):
        # Defer the interaction to prevent timeout
        await interaction.response.defer(ephemeral=True)

        if n < 1 or n > 50:
            await interaction.followup.send(
                "Please provide a number between 1 and 50.", ephemeral=True
            )
            return

        # Fetch the last n messages from the channel
        messages = []
        async for message in interaction.channel.history(limit=n):
            # Skip bot messages and empty messages
            if message.author.bot or not message.content:
                continue
            messages.append(message)

        if not messages:
            await interaction.followup.send(
                "No messages found to translate.", ephemeral=True
            )
            return

        # Reverse to get chronological order (oldest first)
        messages.reverse()

        # Format messages for translation
        message_texts = []
        for msg in messages:
            author_name = msg.author.display_name
            content = msg.content
            message_texts.append(f"{author_name}: {content}")

        conversation = "\n".join(message_texts)

        # Translate using Gemini
        try:
            model = genai.GenerativeModel("gemini-3-flash-preview")
            prompt = (
                "Translate the following Discord conversation to English. "
                "Preserve the author names and maintain the conversation format. "
                "Only translate the message content, not the author names.\n\n"
                f"Conversation:\n{conversation}"
            )
            response = model.generate_content(prompt)
            result = response.text

            # Discord message limit is 2000 characters
            if len(result) > 2000:
                result = result[:1997] + "..."

            await interaction.followup.send(result, ephemeral=True)
        except Exception as e:
            await interaction.followup.send(
                f"Error translating messages: {str(e)}", ephemeral=True
            )


async def setup(bot: BackroomsBot) -> None:
    await bot.add_cog(TranslationCog(bot), guild=bot.backrooms)
