import discord
from discord.ext import commands
import httpx

from bot import BackroomsBot
from consts import GEMINI_TOKEN
from ._config import ConfigCog, Cfg


class LLMCog(ConfigCog):
    proxy_url = Cfg(str)
    botroom_id = Cfg(int, default=1187163442814128128)
    req_timeout = Cfg(int, default=30)

    def __init__(self, bot: BackroomsBot) -> None:
        super().__init__(bot)

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        if message.channel.id != await self.botroom_id:
            return
        if message.author == self.bot.user:
            return
        if message.content.endswith("??"):
            conversation = []
            # If the message is a reply to AI, get the original message and add it to the prompt
            if (
                message.reference
                and message.reference.resolved
                and message.reference.resolved.author == self.bot.user
            ):
                ai_msg = message.reference.resolved
                user_msg_id = message.reference.resolved.reference.message_id
                user_msg = await message.channel.fetch_message(user_msg_id)
                # User question
                conversation.append(
                    {
                        "role": "user",
                        "parts": [{"text": user_msg.content.replace("??", "?")}],
                    }
                )
                # AI answer
                conversation.append(
                    {"role": "model", "parts": [{"text": ai_msg.content}]}
                )
            API_URL = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-pro:generateContent?key={GEMINI_TOKEN}"
            conversation.append(
                {
                    "role": "user",
                    "parts": [{"text": message.content.replace("??", "?")}],
                }
            )
            data = {
                "contents": conversation,
                "safetySettings": [  # Maximum power
                    {
                        "category": "HARM_CATEGORY_SEXUALLY_EXPLICIT",
                        "threshold": "BLOCK_NONE",
                    },
                    {
                        "category": "HARM_CATEGORY_HATE_SPEECH",
                        "threshold": "BLOCK_NONE",
                    },
                    {"category": "HARM_CATEGORY_HARASSMENT", "threshold": "BLOCK_NONE"},
                    {
                        "category": "HARM_CATEGORY_DANGEROUS_CONTENT",
                        "threshold": "BLOCK_NONE",
                    },
                ],
            }
            # US socks5 proxy, because API allows only some regions
            proxy = await self.proxy_url
            async with httpx.AsyncClient(proxy=proxy, verify=False) as ac:
                try:
                    response = await ac.post(API_URL, json=data, timeout=await self.req_timeout)
                except httpx.ReadTimeout:
                    await message.reply('Response timed out')
                    return
            if response.status_code == 200:
                json = response.json()
                try:
                    response = json["candidates"][0]["content"]["parts"][0]["text"]
                except KeyError | IndexError:
                    response = '*Did not get a response*'
                allowed = discord.AllowedMentions(
                    roles=False, everyone=False, users=True, replied_user=True
                )
                await message.reply(response, allowed_mentions=allowed)
            else:
                print(f"LLM failed {response.status_code}: {response.json()}")


async def setup(bot: BackroomsBot) -> None:
    await bot.add_cog(LLMCog(bot), guild=bot.guilds[0])
