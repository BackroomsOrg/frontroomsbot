import discord
from discord.ext import commands
from discord import app_commands
from datetime import datetime, timedelta
from typing import Optional, Literal
import uuid
from zoneinfo import ZoneInfo

from bot import BackroomsBot

prague_tz = ZoneInfo("Europe/Prague")


def ts_to_prague_time(ts: datetime) -> datetime:
    """Convert a UTC timestamp to Prague timezone."""
    if ts.tzinfo is None:
        ts = ts.replace(tzinfo=ZoneInfo("UTC"))
    return ts.astimezone(prague_tz)


def get_drink_emoji(drink_type: Literal["beer", "cider"]) -> str:
    if drink_type == "beer":
        return "🍺"
    elif drink_type == "cider":
        return "🍎"
    else:
        return "🍺"


class BeerTrackerCog(commands.Cog):
    def __init__(self, bot: BackroomsBot) -> None:
        self.bot = bot

    @app_commands.command(
        name="beer", description="Log a beer for yourself or someone else! 🍺"
    )
    @app_commands.describe(
        user="Who drank the beer? (Defaults to you)",
        drink_type="What type of drink? (Defaults to beer, can be cider 🍎 we wont judge you (we will though))",
    )
    async def log_beer(
        self,
        interaction: discord.Interaction,
        user: Optional[discord.User] = None,
        drink_type: Optional[Literal["beer", "cider"]] = "beer",
    ):
        db = self.bot.db
        target_user = user or interaction.user
        current_time = datetime.now()

        # Get or create user's beer data
        user_data = await db.beer_tracker.find_one({"user_id": target_user.id}) or {
            "user_id": target_user.id,
            "username": target_user.name,
            "beers": [],
            "total_beers": 0,
            "total_ciders": 0,
        }

        # Add new beer entry with timestamp and UUID
        beer_id = str(uuid.uuid4())
        user_data["beers"].append(
            {"id": beer_id, "timestamp": current_time, "type": drink_type}
        )

        # update total beers count and username if necessary
        if drink_type == "beer":
            user_data["total_beers"] = user_data.get("total_beers", 0) + 1
        elif drink_type == "cider":
            user_data["total_ciders"] = user_data.get("total_ciders", 0) + 1

        user_data["username"] = target_user.name

        # Save to DB
        await db.beer_tracker.replace_one(
            {"user_id": target_user.id}, user_data, upsert=True
        )

        if drink_type == "beer":
            await interaction.response.send_message(
                f"{target_user.mention} has now drunk **{user_data['total_beers']}** beers total! {get_drink_emoji(drink_type)}"
            )
        elif drink_type == "cider":
            await interaction.response.send_message(
                f"{target_user.mention} has now drunk **{user_data['total_ciders']}** "
                f"ciders total! {get_drink_emoji(drink_type)} (Fuj ble 🤒)"
            )
        else:
            await interaction.response.send_message(
                f"{target_user.mention} has now drunk **{user_data['total_beers']}** beers total! {get_drink_emoji(drink_type)}"
            )

    @app_commands.command(
        name="my_beers",
        description="List your beer logs with UUIDs (used for deletion) (can be cider too)",
    )
    @app_commands.describe(
        limit="Number of beers to show (1-50)",
        page="Page number to view",
        drink_type="What type of drink? (Defaults to beer, can be cider 🍎 )",
    )
    async def my_beers(
        self,
        interaction: discord.Interaction,
        limit: app_commands.Range[int, 1, 50] = 10,
        page: app_commands.Range[int, 1] = 1,
        drink_type: Optional[Literal["beer", "cider", "all"]] = "all",
    ):
        db = self.bot.db
        user_data = await db.beer_tracker.find_one({"user_id": interaction.user.id})
        if not user_data or not user_data["beers"]:
            await interaction.response.send_message(
                "You haven't logged any beers yet! 🚱", ephemeral=True
            )
            return

        if drink_type == "all":
            all_beers = user_data["beers"]
        elif drink_type == "beer":
            all_beers = [
                b for b in user_data["beers"] if b.get("type", "beer") == "beer"
            ]
        elif drink_type == "cider":
            all_beers = [b for b in user_data["beers"] if b.get("type") == "cider"]

        # sort by newest
        all_beers = sorted(all_beers, key=lambda x: x["timestamp"], reverse=True)
        total_beers = len(all_beers)
        total_pages = (total_beers + limit - 1) // limit

        # validate page number
        if page > total_pages:
            await interaction.response.send_message(
                f"Page {page} doesn't exist! There are only {total_pages} page(s) available.",
                ephemeral=True,
            )
            return

        # pagination logic
        start_idx = (page - 1) * limit
        end_idx = start_idx + limit
        paginated_beers = all_beers[start_idx:end_idx]

        # build the embed
        embed = discord.Embed(
            title=f"Your Beer Logs (Page {page}/{total_pages})",
            description=f"Total beers: {total_beers}",
            color=discord.Color.blue(),
        )

        for beer in paginated_beers:
            beer_time = ts_to_prague_time(beer["timestamp"]).strftime("%Y-%m-%d %H:%M")
            drink_type = beer.get("type", "beer")
            emoji = get_drink_emoji(drink_type)
            embed.add_field(
                name=f"{emoji} {beer_time}", value=f"`{beer['id']}`", inline=False
            )

        # add footer for pagination
        footer_parts = []
        if page > 1:
            footer_parts.append(f"Previous: /my_beers page={page-1}")
        if page < total_pages:
            footer_parts.append(f"Next: /my_beers page={page+1}")

        if footer_parts:
            embed.set_footer(text=" | ".join(footer_parts))

        await interaction.response.send_message(embed=embed, ephemeral=True)

    @app_commands.command(
        name="beer_delete", description="Delete a beer entry by its UUID"
    )
    @app_commands.describe(
        beer_uuid="The UUID of the beer to delete",
    )
    async def beer_delete(self, interaction: discord.Interaction, beer_uuid: str):
        db = self.bot.db

        # verify UUID format
        try:
            uuid.UUID(beer_uuid)
        except ValueError:
            await interaction.response.send_message(
                "❌ Invalid beer UUID format!", ephemeral=True
            )
            return

        # find which user owns this beer
        user_data = await db.beer_tracker.find_one({"beers.id": beer_uuid})

        if not user_data:
            await interaction.response.send_message(
                "❌ No beer found with that UUID!", ephemeral=True
            )
            return

        # permission check
        if user_data["user_id"] != interaction.user.id:
            await interaction.response.send_message(
                "❌ You can only delete your own beers!", ephemeral=True
            )
            return

        # remove the beer entry
        updated_beers = [b for b in user_data["beers"] if b["id"] != beer_uuid]

        try:
            deleted_beer = next(b for b in user_data["beers"] if b["id"] == beer_uuid)
        except StopIteration:
            await interaction.response.send_message(
                "❌ No beer found with that UUID!", ephemeral=True
            )
            return

        # recalculate totals
        total_beers = len([b for b in updated_beers if b.get("type", "beer") == "beer"])
        total_ciders = len([b for b in updated_beers if b.get("type") == "cider"])

        # update database
        await db.beer_tracker.update_one(
            {"user_id": user_data["user_id"]},
            {
                "$set": {
                    "beers": updated_beers,
                    "total_beers": total_beers,
                    "total_ciders": total_ciders,
                }
            },
        )

        # build confirmation message
        beer_time = ts_to_prague_time(deleted_beer["timestamp"]).strftime(
            "%Y-%m-%d %H:%M"
        )

        response = [
            f"✅ Successfully deleted beer entry for {interaction.user.mention}!",
            f"**Timestamp:** {beer_time}",
            f"**UUID:** `{beer_uuid}`",
        ]

        await interaction.response.send_message("\n".join(response), ephemeral=True)

    @app_commands.command(name="beer_stats", description="Check beer stats for a user")
    @app_commands.describe(
        user="The user to check (defaults to you)",
        period="Time period to filter (default: all time)",
        drink_type="What type of drink? (Defaults to beer, can be cider 🍎 )",
    )
    async def beer_stats(
        self,
        interaction: discord.Interaction,
        user: Optional[discord.User] = None,
        period: Optional[Literal["day", "week", "month", "year"]] = None,
        drink_type: Optional[Literal["beer", "cider", "all"]] = "all",
    ):
        target_user = user or interaction.user
        db = self.bot.db

        user_data = await db.beer_tracker.find_one({"user_id": target_user.id})

        if not user_data or not user_data["beers"]:
            await interaction.response.send_message(
                f"{target_user.mention} hasn't drunk any beers yet! 🚱"
            )
            return

        # Filter beers by time period if specified
        beers = user_data["beers"]

        if drink_type == "beer":
            beers = [b for b in beers if b.get("type", "beer") == "beer"]
        elif drink_type == "cider":
            beers = [b for b in beers if b.get("type") == "cider"]

        if period:
            now = datetime.now(prague_tz)
            if period == "day":
                cutoff = now - timedelta(days=1)
            elif period == "week":
                cutoff = now - timedelta(weeks=1)
            elif period == "month":
                cutoff = now - timedelta(days=30)
            elif period == "year":
                cutoff = now - timedelta(days=365)

            filtered_beers = [
                b for b in beers if ts_to_prague_time(b["timestamp"]) >= cutoff
            ]
            count = len(filtered_beers)
        else:
            if drink_type == "all":
                count = user_data.get("total_beers", 0) + user_data.get(
                    "total_ciders", 0
                )
            elif drink_type == "beer":
                count = user_data.get("total_beers", 0)
            elif drink_type == "cider":
                count = user_data.get("total_ciders", 0)
            period = "all time"

        await interaction.response.send_message(
            f"**{target_user.name}** has drunk **{count}** beers ({period})! 🍻"
        )

    @app_commands.command(
        name="beer_leaderboard", description="Show the top beer drinkers!"
    )
    @app_commands.describe(
        period="Time period to filter (defaults to all time)",
        limit="How many users to show (defaults to 10)",
        drink_type="What type of drink? (Defaults to beer, can be cider 🍎 )",
    )
    async def beer_leaderboard(
        self,
        interaction: discord.Interaction,
        period: Optional[Literal["day", "week", "month", "year"]] = None,
        limit: Optional[app_commands.Range[int, 1, 30]] = 10,
        drink_type: Optional[Literal["beer", "cider", "all"]] = "all",
    ):
        db = self.bot.db
        all_users = await db.beer_tracker.find().to_list(None)

        if not all_users:
            await interaction.response.send_message("No beers have been logged yet! 🚱")
            return

        # Calculate beer counts for each user (filtering by period if needed)
        leaderboard = []
        for user_data in all_users:
            if not user_data.get("beers"):
                continue

            if drink_type == "beer":
                beers = [
                    b for b in user_data["beers"] if b.get("type", "beer") == "beer"
                ]
            elif drink_type == "cider":
                beers = [b for b in user_data["beers"] if b.get("type") == "cider"]
            else:  # drink_type == "all"
                beers = user_data["beers"]

            if period:
                now = datetime.now(prague_tz)
                if period == "day":
                    # cutoff is the start of today
                    cutoff = now.replace(hour=0, minute=0, second=0, microsecond=0)
                elif period == "week":
                    cutoff = now - timedelta(weeks=1)
                elif period == "month":
                    cutoff = now - timedelta(days=30)
                elif period == "year":
                    cutoff = now - timedelta(days=365)

                filtered_beers = [
                    b for b in beers if ts_to_prague_time(b["timestamp"]) >= cutoff
                ]
                total_count = len(filtered_beers)
            else:
                if drink_type == "all":
                    total_count = user_data.get("total_beers", 0) + user_data.get(
                        "total_ciders", 0
                    )
                elif drink_type == "beer":
                    total_count = user_data.get("total_beers", 0)
                elif drink_type == "cider":
                    total_count = user_data.get("total_ciders", 0)

            if total_count > 0:
                leaderboard.append(
                    (
                        user_data["username"],
                        total_count,
                        user_data["user_id"],
                        user_data["total_beers"],
                        user_data["total_ciders"],
                    )
                )

        # Sort by beer count (descending)
        leaderboard.sort(key=lambda x: x[1], reverse=True)
        leaderboard = leaderboard[:limit]

        if not leaderboard:
            await interaction.response.send_message(
                f"No beers logged in the last {period}! 🚱"
            )
            return

        # Format the leaderboard
        period_str = period if period else "all time"
        embed = discord.Embed(
            title=f"🍺 Top Beer Drinkers ({period_str}) 🍺", color=discord.Color.gold()
        )

        description = []
        for idx, (_, count, user_id, total_beers, total_ciders) in enumerate(
            leaderboard, 1
        ):
            if total_ciders > 0:
                description.append(
                    f"**{idx}.** <@{user_id}> - **{count}** beers ({total_beers} beers, {total_ciders} ciders) 🍻"
                )
            else:
                description.append(f"**{idx}.** <@{user_id}> - **{count}** beers 🍻")

        embed.description = "\n".join(description)
        await interaction.response.send_message(embed=embed)

    @app_commands.command(
        name="beer_last", description="Check when a user last had a beer"
    )
    @app_commands.describe(
        user="The user to check (defaults to you)",
        drink_type="What type of drink? (Defaults to beer, can be cider 🍎 )",
    )
    async def beer_last(
        self,
        interaction: discord.Interaction,
        user: Optional[discord.User] = None,
        drink_type: Optional[Literal["beer", "cider", "all"]] = "all",
    ):
        target_user = user or interaction.user
        db = self.bot.db

        # fetch user data
        user_data = await db.beer_tracker.find_one({"user_id": target_user.id})

        if not user_data or not user_data["beers"]:
            await interaction.response.send_message(
                f"{target_user.name} hasn't drunk any beers yet! 🚱"
            )
            return

        if drink_type == "all":
            last_beer = user_data["beers"][-1]
        elif drink_type == "beer":
            last_beer = [
                b for b in user_data["beers"] if b.get("type", "beer") == "beer"
            ][-1]
        elif drink_type == "cider":
            last_beer = [b for b in user_data["beers"] if b.get("type") == "cider"][-1]

        last_time = ts_to_prague_time(last_beer["timestamp"])
        now = datetime.now(prague_tz)
        time_diff = now - last_time

        # time formatting
        if time_diff < timedelta(minutes=1):
            time_str = "just now"
        elif time_diff < timedelta(hours=1):
            minutes = int(time_diff.total_seconds() // 60)
            time_str = f"{minutes} minute{'s' if minutes != 1 else ''} ago"
        elif time_diff < timedelta(days=1):
            hours = int(time_diff.total_seconds() // 3600)
            time_str = f"{hours} hour{'s' if hours != 1 else ''} ago"
        elif time_diff < timedelta(days=30):
            days = int(time_diff.total_seconds() // 86400)
            time_str = f"{days} day{'s' if days != 1 else ''} ago"
        elif time_diff < timedelta(days=365):
            months = int(time_diff.days // 30)
            time_str = f"{months} month{'s' if months != 1 else ''} ago"
        else:
            years = int(time_diff.days // 365)
            time_str = f"{years} year{'s' if years != 1 else ''} ago"

        # Add exact time for reference
        exact_time = last_time.strftime("%Y-%m-%d %H:%M:%S")

        await interaction.response.send_message(
            f"🍺 {target_user.name}'s last beer was **{time_str}** ({exact_time})"
        )


async def setup(bot: BackroomsBot) -> None:
    await bot.add_cog(BeerTrackerCog(bot), guild=bot.backrooms)
