import os
import discord

from dotenv import load_dotenv

from random import randint

load_dotenv()
TOKEN = os.getenv("DISCORD_TOKEN")
GUILD = os.getenv("GUILD_ID")

intents = discord.Intents.default()
intents.message_content = True
intents.reactions = True
intents.members = True

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


@tree.command(name="sync", description="Sync commands", guild=guild)
async def sync(interaction: discord.Interaction):
    print("Syncing commands")
    ret = await tree.sync(guild=guild)
    print(ret)
    await interaction.response.send_message("Synced!")
    print("Command tree synced")

@tree.command(name="csgoroadtoglobal", description="CSGOROADTOGLOBAL", guild=guild)
async def csgo(interaction: discord.Interaction):
    # gamers and their ids
    gamers = {
        "JosefKuchar": 1019696733019713626,
        "Roytak": 302863931507212298,
        "Soromis": 306158645673197581,
        "TominoBLM": 290511348100628480,
        "Addy Daddy": 262527189507899392,
        "Kubik": 292365427777208322,
        "MrStinky": 474190499964780545
    }

    # create the message and ship it, time to play some cs
    message = f'CSGOROADTOGLOBAL\nNÁSTUP'
    for uid in gamers.values():
        message = message + f' <@{uid}>'
    await interaction.response.send_message(message)

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
async def on_ready():
    print(f"{client.user} has connected to Discord!")


client.run(TOKEN)
