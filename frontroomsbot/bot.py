import datetime
import os
import discord
import httpx

from dotenv import load_dotenv

from random import randint, choices, uniform
from discord import app_commands

load_dotenv()
TOKEN = os.getenv("DISCORD_TOKEN")
GUILD = os.getenv("GUILD_ID")
HF_TOKEN = os.getenv("HF_TOKEN")

intents = discord.Intents.default()
intents.message_content = True
intents.reactions = True

client = discord.Client(intents=intents)
tree = discord.app_commands.CommandTree(client)
guild = discord.Object(id=GUILD)

PIN_COUNT = 5
TIMEOUT_COUNT = 15


@tree.command(name="hello", description="Sends hello!", guild=guild)
async def hello(interaction: discord.Interaction):
    await interaction.response.send_message("Hello!")


@tree.command(name="roll", description="Rolls a number", guild=guild)
async def roll(interaction: discord.Interaction, first: int = 100, second: int = None):
    if second is None:
        result = randint(0, first)

    else:
        if second < first:
            await interaction.response.send_message(
                "Second needs to be higher than first."
            )
            return
        result = randint(first, second)

    await interaction.response.send_message(f"{result}")


@tree.command(name="flip", description="Flips a coin", guild=guild)
async def flip(interaction: discord.Interaction):
    # randint(0, 1) ? "True" : "False" <- same thing
    result = "True" if randint(0, 1) else "False"
    await interaction.response.send_message(f"{result}")


@app_commands.checks.cooldown(1, 60.0)
@tree.command(name="kasparek", description="Zjistí jakého máš kašpárka", guild=guild)
async def kasparek(interaction: discord.Interaction):
    unit = choices(["cm", "mm"], weights=(95, 5), k=1)[0]
    result = round(uniform(0, 50), 2)

    message = f"{result}{unit}" if unit else f"{result}"
    await interaction.response.send_message(message)


@kasparek.error
async def on_kasparek_error(
    interaction: discord.Interaction, error: app_commands.AppCommandError
):
    if isinstance(error, app_commands.CommandOnCooldown):
        await interaction.response.send_message(str(error), ephemeral=True)


@tree.command(name="sync", description="Sync commands", guild=guild)
async def sync(interaction: discord.Interaction):
    print("Syncing commands")
    ret = await tree.sync(guild=guild)
    print(ret)
    await interaction.response.send_message("Synced!")
    print("Command tree synced")


@client.event
async def on_raw_reaction_add(payload: discord.RawReactionActionEvent):
    reaction = payload.emoji.name
    channel = client.get_channel(payload.channel_id)
    message = await channel.fetch_message(payload.message_id)

    user = await client.fetch_user(payload.user_id)

    match reaction:
        case "🔖":
            direct = await user.create_dm()
            await direct.send(message.content)
        case "📌":
            await pin_handle(message, channel)
        case "🔇":
            await timeout_handle(message)
        case _:
            return


async def pin_handle(
    message: discord.message.Message, channel: discord.channel.TextChannel
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
            and react.count >= PIN_COUNT
        ):
            # FIXME
            # pins = await channel.pins()
            # we need to maintain when was the last warning about filled pins,
            # otherwise we will get spammed by the pins full message
            await message.pin()
            break


async def timeout_handle(message: discord.message.Message):
    """Handles auto timeout of users

    :param message: Message that received a reaction
    :return
    """
    for react in message.reactions:
        if (
            react.emoji == "🔇"
            and not message.author.is_timed_out()
            and not message.is_system()
            and react.count >= TIMEOUT_COUNT
        ):
            # FIXME
            # we need to maintain when was the last timeout,
            # otherwise someone could get locked out
            duration = datetime.timedelta(minutes=1)
            await message.author.timeout(duration)
            break


@client.event
async def pin(payload: discord.RawReactionActionEvent):
    reaction = payload.emoji.name
    channel = client.get_channel(payload.channel_id)
    message = await channel.fetch_message(payload.message_id)

    user = await client.fetch_user(payload.user_id)

    match reaction:
        case "🔖":
            direct = await user.create_dm()
            await direct.send(message.content)
        case _:
            return


@client.event
async def on_message(message: discord.Message):
    if message.author == client.user:
        return
    if message.content.endswith("??"):
        API_URL = (
            "https://api-inference.huggingface.co/models/mistralai/Mistral-7B-v0.1"
        )
        prompt = f"""Seš expertní AI, které odpovídá na otázky ohledně různých témat.

[User]: Jaky pouziva https port?
[AI]: Protokol HTTPS používá port 443.
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


@client.event
async def on_ready():
    print(f"{client.user} has connected to Discord!")


client.run(TOKEN)
