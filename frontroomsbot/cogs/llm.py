import discord
from discord.ext import commands
import httpx
import pytz
import datetime

from bot import BackroomsBot
from consts import HF_TOKEN


class LLMCog(commands.Cog):
    def __init__(self, bot: BackroomsBot) -> None:
        self.bot = bot

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        if message.channel.id != 1187163442814128128:  # botrooms
            return
        if message.author == self.bot.user:
            return
        if message.content.endswith("??"):
            pre_question = ""
            # If the message is a reply to AI, get the original message and add it to the prompt
            if (
                message.reference
                and message.reference.resolved
                and message.reference.resolved.author == self.client.user
            ):
                ai_msg = message.reference.resolved
                user_msg_id = message.reference.resolved.reference.message_id
                user_msg = await message.channel.fetch_message(user_msg_id)
                pre_question = f"""
    [User]: {user_msg.content.replace("??", "?")}
    [AI]: {ai_msg.content}"""

            API_URL = (
                "https://api-inference.huggingface.co/models/mistralai/Mistral-7B-v0.1"
            )
            now = datetime.datetime.now(pytz.timezone("Europe/Prague"))
            prompt = f"""Aktuální datum a čas je {now.strftime("%d.%m.%Y %H:%M")}.
    Seš expertní AI, které odpovídá na otázky ohledně různých témat.

    [User]: Jaky pouziva https port?
    [AI]: Protokol HTTPS používá port 443.{pre_question}
    [User]: {message.content.replace("??", "?")}
    [AI]: """
            headers = {"Authorization": f"Bearer {HF_TOKEN}"}
            data = {
                "inputs": prompt,
                "max_new_tokens": 250,  # This is maximum HF API allows
                "options": {"wait_for_model": True},  # Wait if model is not ready
            }
            async with httpx.AsyncClient() as ac:
                response = await ac.post(API_URL, headers=headers, json=data)
            if response.status_code == 200:
                json = response.json()
                raw_text = json[0]["generated_text"]
                # Filter out the prompt
                text = raw_text.replace(prompt, "").strip()
                # Remove new questions hallucinated by model
                text = text.split("\n[User]:")[0]
                allowed = discord.AllowedMentions(
                    roles=False, everyone=False, users=True, replied_user=True
                )
                await message.reply(text, allowed_mentions=allowed)
            else:
                print(f"LLM failed {response.status_code}: {response.json()}")


async def setup(bot: BackroomsBot) -> None:
    await bot.add_cog(LLMCog(bot), guild=bot.guilds[0])
