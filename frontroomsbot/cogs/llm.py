import discord
from discord.ext import commands
import httpx

from bot import BackroomsBot
from consts import GEMINI_TOKEN, GROQ_TOKEN
from ._config import ConfigCog, Cfg


def replace_suffix(message: discord.Message, suffix: str) -> str:
    return message.content[: -len(suffix)] + "?"


class TolerableLLMError(Exception):
    """An error that won't be logged, only sent to the user"""

    pass


class LLMCog(ConfigCog):
    proxy_url = Cfg(str)
    botroom_id = Cfg(int, default=1187163442814128128)
    req_timeout = Cfg(int, default=30)

    def __init__(self, bot: BackroomsBot) -> None:
        super().__init__(bot)

    async def handle_google_gemini(self, conversation: list[dict]):
        API_URL = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-pro:generateContent?key={GEMINI_TOKEN}"
        # Convert conversation to the format required by the API
        conversation = [
            {
                "role": "model" if msg["role"] == "assistant" else "user",
                "parts": [{"text": msg["content"]}],
            }
            for msg in conversation
        ]
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
            response = await ac.post(API_URL, json=data, timeout=await self.req_timeout)
        json = response.json()
        if response.status_code == 200:
            return json["candidates"][0]["content"]["parts"][0]["text"]
        elif response.status_code == 500:
            raise TolerableLLMError(json["error"]["message"])
        else:
            raise RuntimeError(f"Gemini failed {response.status_code}: {json}")

    async def handle_groq(self, model, conversation: list[dict], system_prompt=True):
        API_URL = "https://api.groq.com/openai/v1/chat/completions"
        data = {
            "messages": conversation,
            "model": model,
        }

        if system_prompt:
            data["messages"].insert(
                0,
                {
                    "role": "system",
                    "content": "Jsi digitální asistent, který odpovídá v češtině",
                },
            )

        headers = {
            "Authorization": f"Bearer {GROQ_TOKEN}",
            "Content-Type": "application/json",
        }
        async with httpx.AsyncClient() as ac:
            response = await ac.post(
                API_URL, json=data, headers=headers, timeout=await self.req_timeout
            )
        json = response.json()
        if response.status_code == 200:
            return json["choices"][0]["message"]["content"]
        else:
            raise RuntimeError(f"Groq failed {response.status_code}: {json}")

    async def handle_llama(self, conversation: list[dict]):
        return await self.handle_groq(
            "meta-llama/llama-4-maverick-17b-128e-instruct",
            conversation,
            system_prompt=False,
        )

    async def handle_gemma(self, conversation: list[dict]):
        return await self.handle_groq("gemma2-9b-it", conversation)

    async def handle_reasoning(self, conversation: list[dict]):
        return await self.handle_groq(
            "deepseek-r1-distill-llama-70b", conversation, system_prompt=False
        )

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        suffix_map = {
            "??": self.handle_google_gemini,
            "?!": self.handle_llama,
            "?.": self.handle_gemma,
            "?r": self.handle_reasoning,
        }

        if message.channel.id != await self.botroom_id:
            return
        if message.author == self.bot.user:
            return
        for suffix, handler in suffix_map.items():
            if message.content.endswith(suffix):
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
                        {"role": "user", "content": replace_suffix(user_msg, suffix)}
                    )
                    # AI answer
                    conversation.append(
                        {"role": "assistant", "content": ai_msg.content}
                    )

                conversation.append(
                    {"role": "user", "content": replace_suffix(message, suffix)}
                )

                try:
                    response = await handler(conversation)
                    allowed = discord.AllowedMentions(
                        roles=False, everyone=False, users=True, replied_user=True
                    )
                    chunks = [
                        response[i : i + 2000] for i in range(0, len(response), 2000)
                    ]
                    for chunk in chunks:
                        await message.reply(chunk, allowed_mentions=allowed)
                except httpx.ReadTimeout:
                    await message.reply("*Response timed out*")
                except (KeyError, IndexError):
                    await message.reply("*Did not get a response*")
                except TolerableLLMError as e:
                    await message.reply(f"*{str(e)}*")
                except RuntimeError as e:
                    await message.reply(f"*{str(e)}*")
                    raise RuntimeError(e)


async def setup(bot: BackroomsBot) -> None:
    await bot.add_cog(LLMCog(bot), guild=bot.backrooms)
