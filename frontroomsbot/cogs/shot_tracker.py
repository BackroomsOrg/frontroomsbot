import discord
from discord.ext import commands
from discord import app_commands
from datetime import datetime, timedelta
from typing import Optional, Literal
import uuid
from zoneinfo import ZoneInfo

from bot import BackroomsBot

prague_tz = ZoneInfo("Europe/Prague")

# Constants for shot volumes (in liters)
FULL_SHOT_VOLUME = 0.05  # 0.5dl
HALF_SHOT_VOLUME = 0.025  # 0.25dl


def ts_to_prague_time(ts: datetime) -> datetime:
    """Convert a UTC timestamp to Prague timezone."""
    if ts.tzinfo is None:
        ts = ts.replace(tzinfo=ZoneInfo("UTC"))
    return ts.astimezone(prague_tz)


def format_volume(volume_liters: float) -> str:
    """Format volume in liters to a readable string."""
    ml = volume_liters * 1000
    if ml >= 1000:
        return f"{volume_liters:.2f}L"
    else:
        return f"{ml:.0f}ml"

class ShotTrackerCog(commands.Cog):
    def __init__(self, bot: BackroomsBot) -> None:
        self.bot = bot

    async def _log_shot(
        self,
        user: discord.User,
        volume: float,
        shot_type: str,
    ):
        db = self.bot.db
        target_user = user
        current_time = datetime.now()

        # Get or create user's shot data
        user_data = await db.shot_tracker.find_one({"user_id": target_user.id}) or {
            "user_id": target_user.id,
            "username": target_user.name,
            "shots": [],
            "total_shots": 0,
            "total_volume": 0.0,
        }

        # Add new shot entry
        shot_id = str(uuid.uuid4())
        user_data["shots"].append({
            "id": shot_id,
            "timestamp": current_time,
            "volume": volume,
            "type": shot_type,
        })

        # Update totals and username
        user_data["total_shots"] += 1
        user_data["total_volume"] += volume
        user_data["username"] = target_user.name

        # Save to DB
        await db.shot_tracker.replace_one(
            {"user_id": target_user.id}, user_data, upsert=True
        )
        
        return user_data
    
    @app_commands.command(
        name="shot", description="Log a shot for yourself or someone else!"
    )
    @app_commands.describe(user="Who drank the shot? (Defaults to you)")
    async def log_shot(
        self, interaction: discord.Interaction, user: Optional[discord.User] = None
    ):
        target_user = user or interaction.user
        user_data = await self._log_shot(target_user, FULL_SHOT_VOLUME, "full_shot")

        await interaction.response.send_message(
            f"{target_user.mention} has now drunk **{user_data['total_shots']}** shots "
            f"(**{format_volume(user_data['total_volume'])}** total)!"
        )

    @app_commands.command(
        name="half_shot", description="Log a half shot for yourself or someone else!"
    )
    @app_commands.describe(user="Who drank the half shot? (Defaults to you)")
    async def log_half_shot(
        self, interaction: discord.Interaction, user: Optional[discord.User] = None
    ):
        target_user = user or interaction.user
        user_data = await self._log_shot(target_user, HALF_SHOT_VOLUME, "half_shot")

        await interaction.response.send_message(
            f"{target_user.mention} has now drunk **{user_data['total_shots']}** shots "
            f"(**{format_volume(user_data['total_volume'])}** total)!"
        )
    
    @app_commands.command(
        name="mass_shot", description="Log a shot for multiple users at once!"
    )
    @app_commands.describe(
        users="Select all the people who drank together"
    )
    async def mass_shot(
        self, interaction: discord.Interaction, users: list[discord.User], volume: Optional[Literal["half", "full"]] = "full"
    ):
        if not users:
            await interaction.response.send_message(
                "❌ You must mention at least one user!", ephemeral=True
            )
            return

        # loop through mentioned users
        for target_user in users:
            await self._log_shot(
                user=target_user,
                volume=FULL_SHOT_VOLUME if volume == "full" else HALF_SHOT_VOLUME,
                shot_type="full_shot" if volume == "full" else "half_shot"
            )

        await interaction.response.send_message(
            f"🥃 Shots were logged for **{len(users)}** people!"
        )

    # Aliases for shot commands
    @app_commands.command(
        name="poldeci", description="Log a shot for yourself or someone else!"
    )
    @app_commands.describe(user="Who drank the shot? (Defaults to you)")
    async def shot_alias(
        self, interaction: discord.Interaction, user: Optional[discord.User] = None
    ):
        await self.log_shot(interaction, user)

    @app_commands.command(
        name="stamprlik", description="Log a half shot for yourself or someone else!"
    )
    @app_commands.describe(user="Who drank the half shot? (Defaults to you)")
    async def half_shot_alias(
        self, interaction: discord.Interaction, user: Optional[discord.User] = None
    ):
        await self.log_half_shot(interaction, user)

    @app_commands.command(
        name="my_shots",
        description="List your shot logs with UUIDs (used for deletion)",
    )
    @app_commands.describe(
        limit="Number of shots to show (1-50)", page="Page number to view"
    )
    async def my_shots(
        self,
        interaction: discord.Interaction,
        limit: app_commands.Range[int, 1, 50] = 10,
        page: app_commands.Range[int, 1] = 1,
    ):
        db = self.bot.db
        user_data = await db.shot_tracker.find_one({"user_id": interaction.user.id})
        if not user_data or not user_data["shots"]:
            await interaction.response.send_message(
                "You haven't logged any shots yet! 🚱", ephemeral=True
            )
            return

        # Sort by newest
        all_shots = sorted(
            user_data["shots"], key=lambda x: x["timestamp"], reverse=True
        )
        total_shots = len(all_shots)
        total_pages = (total_shots + limit - 1) // limit

        # Validate page number
        if page > total_pages:
            await interaction.response.send_message(
                f"Page {page} doesn't exist! There are only {total_pages} page(s) available.",
                ephemeral=True,
            )
            return

        # Pagination logic
        start_idx = (page - 1) * limit
        end_idx = start_idx + limit
        paginated_shots = all_shots[start_idx:end_idx]

        # Build the embed
        embed = discord.Embed(
            title=f"Your Shot Logs (Page {page}/{total_pages})",
            description=f"Total shots: {total_shots} | Total volume: {format_volume(user_data.get('total_volume', 0))}",
            color=discord.Color.orange(),
        )

        for shot in paginated_shots:
            shot_time = ts_to_prague_time(shot["timestamp"]).strftime("%Y-%m-%d %H:%M")
            shot_type = "🥃" if shot.get("type") == "full_shot" else "🥃½"
            volume_str = format_volume(shot.get("volume", FULL_SHOT_VOLUME))
            embed.add_field(
                name=f"{shot_type} {shot_time} ({volume_str})",
                value=f"`{shot['id']}`",
                inline=False
            )

        # Add footer for pagination
        footer_parts = []
        if page > 1:
            footer_parts.append(f"Previous: /my_shots page={page-1}")
        if page < total_pages:
            footer_parts.append(f"Next: /my_shots page={page+1}")

        if footer_parts:
            embed.set_footer(text=" | ".join(footer_parts))

        await interaction.response.send_message(embed=embed, ephemeral=True)

    @app_commands.command(
        name="shot_delete", description="Delete a shot entry by its UUID"
    )
    @app_commands.describe(
        shot_uuid="The UUID of the shot to delete",
    )
    async def shot_delete(self, interaction: discord.Interaction, shot_uuid: str):
        db = self.bot.db

        # Verify UUID format
        try:
            uuid.UUID(shot_uuid)
        except ValueError:
            await interaction.response.send_message(
                "❌ Invalid shot UUID format!", ephemeral=True
            )
            return

        # Find which user owns this shot
        user_data = await db.shot_tracker.find_one({"shots.id": shot_uuid})

        if not user_data:
            await interaction.response.send_message(
                "❌ No shot found with that UUID!", ephemeral=True
            )
            return

        # Permission check
        if user_data["user_id"] != interaction.user.id:
            await interaction.response.send_message(
                "❌ You can only delete your own shots!", ephemeral=True
            )
            return

        # Find the shot to delete
        try:
            deleted_shot = next(s for s in user_data["shots"] if s["id"] == shot_uuid)
        except StopIteration:
            await interaction.response.send_message(
                "❌ No shot found with that UUID!", ephemeral=True
            )
            return

        # Remove the shot entry
        updated_shots = [s for s in user_data["shots"] if s["id"] != shot_uuid]
        new_total_volume = sum(s.get("volume", FULL_SHOT_VOLUME) for s in updated_shots)

        # Update database
        await db.shot_tracker.update_one(
            {"user_id": user_data["user_id"]},
            {
                "$set": {
                    "shots": updated_shots,
                    "total_shots": len(updated_shots),
                    "total_volume": new_total_volume
                }
            },
        )

        # Build confirmation message
        shot_time = ts_to_prague_time(deleted_shot["timestamp"]).strftime(
            "%Y-%m-%d %H:%M"
        )
        shot_type = "Full shot" if deleted_shot.get("type") == "full_shot" else "Half shot"
        volume_str = format_volume(deleted_shot.get("volume", FULL_SHOT_VOLUME))

        response = [
            f"✅ Successfully deleted shot entry for {interaction.user.mention}!",
            f"**Type:** {shot_type} ({volume_str})",
            f"**Timestamp:** {shot_time}",
            f"**UUID:** `{shot_uuid}`",
        ]

        await interaction.response.send_message("\n".join(response), ephemeral=True)

    @app_commands.command(name="shot_stats", description="Check shot stats for a user")
    @app_commands.describe(
        user="The user to check (defaults to you)",
        period="Time period to filter (default: all time)",
    )
    async def shot_stats(
        self,
        interaction: discord.Interaction,
        user: Optional[discord.User] = None,
        period: Optional[Literal["day", "week", "month", "year"]] = None,
    ):
        target_user = user or interaction.user
        db = self.bot.db

        user_data = await db.shot_tracker.find_one({"user_id": target_user.id})

        if not user_data or not user_data["shots"]:
            await interaction.response.send_message(
                f"{target_user.mention} hasn't drunk any shots yet! 🚱"
            )
            return

        # Filter shots by time period if specified
        shots = user_data["shots"]
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

            filtered_shots = [
                s for s in shots if ts_to_prague_time(s["timestamp"]) >= cutoff
            ]
            count = len(filtered_shots)
            volume = sum(s.get("volume", FULL_SHOT_VOLUME) for s in filtered_shots)
        else:
            count = user_data["total_shots"]
            volume = user_data.get("total_volume", 0)
            period = "all time"

        await interaction.response.send_message(
            f"**{target_user.name}** has drunk **{count}** shots "
            f"(**{format_volume(volume)}**) ({period})! 🥃"
        )

    @app_commands.command(
        name="shot_leaderboard", description="Show the top shot drinkers!"
    )
    @app_commands.describe(
        period="Time period to filter (defaults to all time)",
        limit="How many users to show (defaults to 10)",
        sort_by="Sort by shot count or total volume",
    )
    async def shot_leaderboard(
        self,
        interaction: discord.Interaction,
        period: Optional[Literal["day", "week", "month", "year"]] = None,
        limit: Optional[app_commands.Range[int, 1, 30]] = 10,
        sort_by: Optional[Literal["count", "volume"]] = "volume",
    ):
        db = self.bot.db
        all_users = await db.shot_tracker.find().to_list(None)

        if not all_users:
            await interaction.response.send_message("No shots have been logged yet! 🚱")
            return

        # Calculate shot counts and volumes for each user
        leaderboard = []
        for user_data in all_users:
            if not user_data.get("shots"):
                continue

            if period:
                now = datetime.now(prague_tz)
                if period == "day":
                    cutoff = now.replace(hour=0, minute=0, second=0, microsecond=0)
                elif period == "week":
                    cutoff = now - timedelta(weeks=1)
                elif period == "month":
                    cutoff = now - timedelta(days=30)
                elif period == "year":
                    cutoff = now - timedelta(days=365)

                filtered_shots = [
                    s for s in user_data["shots"]
                    if ts_to_prague_time(s["timestamp"]) >= cutoff
                ]
                count = len(filtered_shots)
                volume = sum(s.get("volume", FULL_SHOT_VOLUME) for s in filtered_shots)
            else:
                count = user_data["total_shots"]
                volume = user_data.get("total_volume", 0)

            if count > 0:
                leaderboard.append((user_data["username"], count, volume, user_data["user_id"]))

        # Sort by count or volume
        if sort_by == "volume":
            leaderboard.sort(key=lambda x: x[2], reverse=True)  # Sort by volume
        else:
            leaderboard.sort(key=lambda x: x[1], reverse=True)  # Sort by count

        leaderboard = leaderboard[:limit]

        if not leaderboard:
            await interaction.response.send_message(
                f"No shots logged in the last {period}! 🚱"
            )
            return

        # Format the leaderboard
        period_str = period if period else "all time"
        sort_str = "volume" if sort_by == "volume" else "count"
        embed = discord.Embed(
            title=f"🥃 Top Shot Drinkers by {sort_str} ({period_str}) 🥃",
            color=discord.Color.gold()
        )

        description = []
        for idx, (_, count, volume, user_id) in enumerate(leaderboard, 1):
            if sort_by == "volume":
                description.append(f"**{idx}.** <@{user_id}> - **{format_volume(volume)}** ({count} shots) 🥃")
            else:
                description.append(f"**{idx}.** <@{user_id}> - **{count}** shots ({format_volume(volume)}) 🥃")

        embed.description = "\n".join(description)
        await interaction.response.send_message(embed=embed)

    @app_commands.command(
        name="shot_last", description="Check when a user last had a shot"
    )
    @app_commands.describe(user="The user to check (defaults to you)")
    async def shot_last(
        self, interaction: discord.Interaction, user: Optional[discord.User] = None
    ):
        target_user = user or interaction.user
        db = self.bot.db

        # Fetch user data
        user_data = await db.shot_tracker.find_one({"user_id": target_user.id})

        if not user_data or not user_data["shots"]:
            await interaction.response.send_message(
                f"{target_user.name} hasn't drunk any shots yet! 🚱"
            )
            return

        last_shot = user_data["shots"][-1]
        last_time = ts_to_prague_time(last_shot["timestamp"])
        now = datetime.now(prague_tz)
        time_diff = now - last_time

        # Time formatting
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

        exact_time = last_time.strftime("%Y-%m-%d %H:%M:%S")

        await interaction.response.send_message(
            f"🥃 {target_user.name}'s last shot was a **{time_str}** ({exact_time}) "
        )


async def setup(bot: BackroomsBot) -> None:
    await bot.add_cog(ShotTrackerCog(bot), guild=bot.backrooms)