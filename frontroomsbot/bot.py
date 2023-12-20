import os
import discord
import httpx

from dotenv import load_dotenv

from random import randint, choice, uniform

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


@tree.command(name="kasparek", description="Zjistí jakého máš kašpara", guild=guild)
async def kasparek(interaction: discord.Interaction):
    unit = choice(["m", "cm", "mm", "nm"])
    result = round(uniform(0, 50), 5)

    message = f"{result} {unit}" if unit else f"{result}"
    await interaction.response.send_message(message)


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
            await message.reply(text)


@client.event
async def on_ready():
    print(f"{client.user} has connected to Discord!")


client.run(TOKEN)
