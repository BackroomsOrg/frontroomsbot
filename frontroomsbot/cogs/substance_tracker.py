import discord
from discord.ext import commands
from discord import app_commands
from datetime import datetime, timedelta
from typing import Optional, Literal
import uuid
from zoneinfo import ZoneInfo

from bot import BackroomsBot

prague_tz = ZoneInfo("Europe/Prague")

SUBSTANCE_TYPES = {
    "alcohol": {
        "name": "Alcohol",
    },
    "kratom": {
        "name": "Kratom",
    },
    "cannabis": {
        "name": "Cannabis",
    },
    "caffeine": {
        "name": "Caffeine",
    },
}

SUBSTANCES = {
    "beer": {
        "name": "Beer",
        "emoji": "🍺",
        "type": "alcohol",
        "quantity_unit": "0.5L glass",
        "default_quantity": 1.0,
        # 5% ABV, 0.5L glass, 789 g/L density
        "to_base_units": lambda quantity: quantity * 0.5 * 0.05 * 789,
    },
    "wine": {
        "name": "Wine",
        "emoji": "🍷",
        "type": "alcohol",
        "quantity_unit": "0.15L glass",
        "default_quantity": 1.0,
        # 12% ABV, 0.15L glass, 789 g/L density
        "to_base_units": lambda quantity: quantity * 0.15 * 0.12 * 789,
    },
    "shot": {
        "name": "Shot",
        "emoji": "🥃",
        "type": "alcohol",
        "quantity_unit": "0.04L shot",
        "default_quantity": 1.0,
        # 40% ABV, 0.04L shot, 789 g/L
        "to_base_units": lambda quantity: quantity * 0.04 * 0.40 * 789,
    },
    "kratom": {
        "name": "Kratom",
        "emoji": "🌿",
        "type": "kratom",
        "quantity_unit": "grams",
        "default_quantity": 2.0,
        "to_base_units": lambda quantity: quantity,
    },
    "joint": {
        "name": "Joint",
        "emoji": "🍃",
        "type": "cannabis",
        "quantity_unit": "count",
        "default_quantity": 1.0,
        # 200mg grams of cannabis per person, 20% THC, bioavailability 25%
        "to_base_units": lambda quantity: quantity * 0.2 * 200 * 0.25,
    },
    "cannabis_mg": {
        "name": "Cannabis",
        "emoji": "🍃",
        "type": "cannabis",
        "quantity_unit": "mg",
        "default_quantity": 10.0,
        # Does not account for bioavailability
        "to_base_units": lambda quantity: quantity,
    },
    "coffee": {
        "name": "Coffee",
        "emoji": "☕",
        "type": "caffeine",
        "quantity_unit": "cup",
        "default_quantity": 1.0,
        # 80mg caffeine per cup
        "to_base_units": lambda quantity: quantity * 80,
    },
    "caffeine_mg": {
        "name": "Caffeine",
        "emoji": "☕",
        "type": "caffeine",
        "quantity_unit": "mg",
        "default_quantity": 175.0,
        "to_base_units": lambda quantity: quantity,
    },
    "energy_drink": {
        "name": "Energy Drink",
        "emoji": "🧃",
        "type": "caffeine",
        "quantity_unit": "160mg can",
        "default_quantity": 1.0,
        # 160mg caffeine per can
        "to_base_units": lambda quantity: quantity * 160,
    },
}

TYPE_CHOICES = [
    app_commands.Choice(name=info["name"], value=key)
    for key, info in SUBSTANCE_TYPES.items()
]

SUBSTANCE_CHOICES = [
    app_commands.Choice(name=f"{info['emoji']} {info['name']}", value=key)
    for key, info in SUBSTANCES.items()
]


def ts_to_prague_time(ts: datetime) -> datetime:
    """Convert a UTC timestamp to Prague timezone."""
    if ts.tzinfo is None:
        ts = ts.replace(tzinfo=ZoneInfo("UTC"))
    return ts.astimezone(prague_tz)


def make_log_callback(substance_name: str):
    definition = SUBSTANCES[substance_name]

    @app_commands.describe(
        quantity=f"How many {definition['quantity_unit']} of {definition['emoji']} ?",
        user=f"Who consumed the {definition['emoji']}? (Defaults to you)",
    )
    async def callback(
        interaction: discord.Interaction,
        quantity: float = 1.0,
        user: Optional[discord.User] = None,
    ):
        await interaction.response.send_message(
            f"Logged {quantity} {definition['quantity_unit']} of {substance_name} for {interaction.user.mention}!"
        )

    return callback


class SubstanceTrackerCog(commands.Cog):
    def __init__(self, bot: BackroomsBot) -> None:
        self.bot = bot

    @app_commands.command(
        name="my_substances",
        description="List your substance logs with UUIDs",
    )
    @app_commands.describe(
        limit="Number of substances to show", page="Page number to view"
    )
    async def my_substances(
        self,
        interaction: discord.Interaction,
        limit: app_commands.Range[int, 1, 50] = 10,
        page: app_commands.Range[int, 1] = 1,
    ):
        # TODO
        return

    @app_commands.command(
        name="substance_delete",
        description="Delete a substance entry by its UUID",
    )
    @app_commands.describe(
        substance_uuid="The UUID of the substance entry to delete",
    )
    async def substance_delete(
        self, interaction: discord.Interaction, substance_uuid: str
    ):
        # TODO
        return

    @app_commands.command(
        name="leaderboard",
        description="Show the top consumers of a substance",
    )
    @app_commands.describe(
        substance="The substance to show the leaderboard for",
        period="Time period to filter (defaults to all time)",
        limit="How many users to show (defaults to 10)",
    )
    @app_commands.choices(
        substance=SUBSTANCE_CHOICES,
    )
    async def leaderboard(
        self,
        interaction: discord.Interaction,
        substance: app_commands.Choice[str],
        period: Optional[Literal["day", "week", "month", "year"]] = None,
        limit: Optional[app_commands.Range[int, 1, 30]] = 10,
    ):
        # TODO
        return


async def setup(bot: BackroomsBot) -> None:
    for substance, definition in SUBSTANCES.items():
        callback = make_log_callback(substance)
        command = app_commands.Command(
            name=substance,
            description=f"Log {definition['name']} ({definition['quantity_unit']}) {definition['emoji']} consumption",
            callback=callback,
        )
        bot.tree.add_command(command, guild=bot.backrooms)

    await bot.add_cog(SubstanceTrackerCog(bot), guild=bot.backrooms)
