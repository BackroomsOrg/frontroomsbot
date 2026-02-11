import httpx
import discord
from discord import app_commands
from discord.ext import commands
from discord.ui import Select, View, Modal, TextInput

from bot import BackroomsBot
from consts import RESERVATION_AGENT_TOKEN

PLACE_API_URL = "https://reservation-agent.krejzac.cz/research_business"

MAX_USER_EVENTS = 10


class EventSelectView(View):
    def __init__(
        self, events: list[dict], action: str, cog: "EventsCog", user_id: int
    ) -> None:
        super().__init__(timeout=60)
        self.cog = cog
        self.user_id = user_id
        self.action = action
        self.events = {str(e["message_id"]): e for e in events}

        options = [
            discord.SelectOption(
                label=e.get("name", "Bez názvu")[:100],
                description=f"📍 {e.get('place', '?')[:50]} | 📅 {e.get('date', '?')[:50]}",
                value=str(e["message_id"]),
            )
            for e in events
        ]

        select = Select(
            placeholder="Vyber event...",
            options=options,
            custom_id="event_select",
        )
        select.callback = self.select_callback
        self.add_item(select)

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.user_id:
            await interaction.response.send_message(
                "Toto menu není pro tebe.", ephemeral=True
            )
            return False
        return True

    async def select_callback(self, interaction: discord.Interaction) -> None:
        select = interaction.data["values"][0]
        event = self.events.get(select)

        if event is None:
            await interaction.response.send_message("Event nenalezen.", ephemeral=True)
            return

        if self.action == "cancel":
            await self.cog.do_cancel_event(interaction, event)
        elif self.action == "edit":
            modal = EditEventModal(event, self.cog)
            await interaction.response.send_modal(modal)
        elif self.action == "get_place":
            await self.cog.do_get_place(interaction, event)


class EditEventModal(Modal, title="Upravit event"):
    def __init__(self, event: dict, cog: "EventsCog") -> None:
        super().__init__()
        self.event = event
        self.cog = cog

        self.name_input = TextInput(
            label="Název",
            default=event.get("name", ""),
            required=False,
            max_length=256,
        )
        self.place_input = TextInput(
            label="Místo",
            default=event.get("place", ""),
            required=False,
            max_length=256,
        )
        self.date_input = TextInput(
            label="Datum",
            default=event.get("date", ""),
            required=False,
            max_length=256,
        )
        place_info = event.get("place_info") or {}
        self.phone_input = TextInput(
            label="Telefon",
            default=place_info.get("phone", ""),
            required=False,
            max_length=50,
        )
        self.add_item(self.name_input)
        self.add_item(self.place_input)
        self.add_item(self.date_input)
        self.add_item(self.phone_input)

    async def on_submit(self, interaction: discord.Interaction) -> None:
        name = self.name_input.value or None
        place = self.place_input.value or None
        date = self.date_input.value or None
        phone = self.phone_input.value or None

        await self.cog.do_edit_event(interaction, self.event, name, place, date, phone)


class EventsCog(commands.Cog):
    def __init__(self, bot: BackroomsBot) -> None:
        self.bot = bot

    async def get_user_events(
        self, user_id: int, limit: int = MAX_USER_EVENTS
    ) -> list[dict]:
        db = self.bot.db
        cursor = db.events.find({"creator_id": user_id}).sort("_id", -1).limit(limit)
        return await cursor.to_list(length=limit)

    @app_commands.command(name="create_event", description="Create a new event")
    @app_commands.describe(
        name="Name of the event",
        place="Where the event will take place",
        date="When the event will happen (include time if needed)",
    )
    async def create_event(
        self, interaction: discord.Interaction, name: str, place: str, date: str
    ) -> None:
        embed = discord.Embed(
            title=name,
            description=f"📍 **{place}**",
            color=discord.Color.blurple(),
        )
        embed.add_field(name="📅 Datum", value=date, inline=False)
        embed.add_field(name="👤 Vytvořil", value=interaction.user.mention, inline=False)
        embed.add_field(name="👍 Zúčastní se", value="_žádní uživatelé_", inline=False)
        embed.add_field(name="🤷 Možná", value="_žádní uživatelé_", inline=False)
        embed.add_field(name="❌ Neúčastní se", value="_žádní uživatelé_", inline=False)

        await interaction.response.send_message(embed=embed)
        message = await interaction.original_response()

        db = self.bot.db
        event_data = {
            "message_id": message.id,
            "channel_id": message.channel.id,
            "name": name,
            "place": place,
            "date": date,
            "creator_id": interaction.user.id,
            "reactions": {
                "👍": [],
                "🤷": [],
                "❌": [],
            },
        }
        await db.events.insert_one(event_data)

        await message.add_reaction("👍")
        await message.add_reaction("🤷")
        await message.add_reaction("❌")

    @app_commands.command(
        name="edit_event", description="Edit an existing event (creator only)"
    )
    async def edit_event(self, interaction: discord.Interaction) -> None:
        events = await self.get_user_events(interaction.user.id)

        if not events:
            await interaction.response.send_message(
                "Nemáš žádné eventy k úpravě.", ephemeral=True
            )
            return

        view = EventSelectView(events, "edit", self, interaction.user.id)
        await interaction.response.send_message(
            "Vyber event k úpravě:", view=view, ephemeral=True
        )

    async def do_edit_event(
        self,
        interaction: discord.Interaction,
        event: dict,
        name: str | None,
        place: str | None,
        date: str | None,
        phone: str | None = None,
    ) -> None:
        event_message_id = event["message_id"]

        updates = {}
        if name:
            updates["name"] = name
        if place:
            updates["place"] = place
        if date:
            updates["date"] = date
        if phone:
            updates["place_info.phone"] = phone

        if not updates:
            await interaction.response.send_message(
                "Nebyly provedeny žádné změny.", ephemeral=True
            )
            return

        db = self.bot.db
        await db.events.update_one(
            {"message_id": event_message_id},
            {"$set": updates},
        )

        channel = self.bot.get_channel(event.get("channel_id"))
        if channel is not None:
            try:
                message = await channel.fetch_message(event_message_id)
                if message is not None and message.embeds:
                    embed = message.embeds[0]
                    if name:
                        embed.title = name
                    if place:
                        embed.description = f"📍 **{place}**"
                    if date:
                        for i, field in enumerate(embed.fields):
                            if field.name == "📅 Datum":
                                embed.set_field_at(i, name="📅 Datum", value=date)
                                break
                    if phone:
                        desc = embed.description or ""
                        if "📞" in desc:
                            lines = desc.split("\n")
                            lines = [line for line in lines if not line.startswith("📞")]
                            lines.append(f"📞 {phone}")
                            embed.description = "\n".join(lines)
                        else:
                            embed.description = f"{desc}\n📞 {phone}"
                    await message.edit(embed=embed)
            except Exception:
                pass

        await interaction.response.send_message(
            "Event úspěšně upraven!", ephemeral=True
        )

    @app_commands.command(
        name="cancel_event", description="Cancel an event (creator only)"
    )
    async def cancel_event(self, interaction: discord.Interaction) -> None:
        events = await self.get_user_events(interaction.user.id)

        if not events:
            await interaction.response.send_message(
                "Nemáš žádné eventy ke zrušení.", ephemeral=True
            )
            return

        view = EventSelectView(events, "cancel", self, interaction.user.id)
        await interaction.response.send_message(
            "Vyber event ke zrušení:", view=view, ephemeral=True
        )

    async def do_cancel_event(
        self, interaction: discord.Interaction, event: dict
    ) -> None:
        db = self.bot.db
        await db.events.delete_one({"message_id": event["message_id"]})

        embed = discord.Embed(
            title="Event zrušen",
            description=f"**{event['name']}** byl zrušen.",
            color=discord.Color.red(),
        )
        embed.add_field(name="📍 Místo", value=event["place"], inline=False)
        embed.add_field(name="📅 Datum", value=event["date"], inline=False)

        await interaction.response.send_message(embed=embed)

    @app_commands.command(
        name="event_get_place",
        description="Fetch detailed place info for an event (creator only)",
    )
    async def event_get_place(self, interaction: discord.Interaction) -> None:
        events = await self.get_user_events(interaction.user.id)

        if not events:
            await interaction.response.send_message(
                "Nemáš žádné eventy.", ephemeral=True
            )
            return

        view = EventSelectView(events, "get_place", self, interaction.user.id)
        await interaction.response.send_message(
            "Vyber event pro získání informací o místě:", view=view, ephemeral=True
        )

    async def do_get_place(
        self, interaction: discord.Interaction, event: dict
    ) -> None:
        place = event.get("place", "")
        if not place:
            await interaction.response.send_message(
                "Event nemá nastavené místo.", ephemeral=True
            )
            return

        await interaction.response.defer(ephemeral=True)

        try:
            async with httpx.AsyncClient(timeout=30) as client:
                response = await client.post(
                    PLACE_API_URL,
                    json={"prompt": place},
                    headers={
                        "Content-Type": "application/json",
                        "Accept": "*/*",
                        "x-magic": RESERVATION_AGENT_TOKEN or "",
                    },
                )
                response.raise_for_status()
                data = response.json()
        except httpx.HTTPStatusError as e:
            await interaction.followup.send(
                f"API vrátilo chybu: {e.response.status_code}", ephemeral=True
            )
            return
        except Exception as e:
            await interaction.followup.send(
                f"Nepodařilo se získat informace o místě: {e}", ephemeral=True
            )
            return

        channel = self.bot.get_channel(event.get("channel_id"))
        if channel is None:
            await interaction.followup.send(
                "Nepodařilo se najít kanál s eventem.", ephemeral=True
            )
            return

        try:
            message = await channel.fetch_message(event["message_id"])
        except Exception:
            await interaction.followup.send(
                "Nepodařilo se najít zprávu s eventem.", ephemeral=True
            )
            return

        if not message.embeds:
            await interaction.followup.send(
                "Event nemá embed.", ephemeral=True
            )
            return

        embed = message.embeds[0]

        place_info_parts = []
        if data.get("name"):
            place_info_parts.append(f"**{data['name']}**")
        if data.get("address"):
            place_info_parts.append(f"📍 {data['address']}")
        if data.get("phone"):
            place_info_parts.append(f"📞 {data['phone']}")
        if data.get("website"):
            place_info_parts.append(f"🌐 {data['website']}")
        if data.get("openingHours"):
            place_info_parts.append(f"🕐 {data['openingHours']}")

        place_info = "\n".join(place_info_parts) if place_info_parts else place
        embed.description = place_info

        if data.get("description"):
            existing_field_names = [f.name for f in embed.fields]
            if "ℹ️ Popis" not in existing_field_names:
                embed.insert_field_at(
                    0, name="ℹ️ Popis", value=data["description"][:1024], inline=False
                )
            else:
                for i, field in enumerate(embed.fields):
                    if field.name == "ℹ️ Popis":
                        embed.set_field_at(
                            i, name="ℹ️ Popis", value=data["description"][:1024], inline=False
                        )
                        break

        await message.edit(embed=embed)

        db = self.bot.db
        await db.events.update_one(
            {"message_id": event["message_id"]},
            {"$set": {"place_info": data, "researched": True}},
        )

        await interaction.followup.send(
            "Informace o místě byly přidány k eventu!", ephemeral=True
        )

    @commands.Cog.listener()
    async def on_raw_reaction_add(self, payload: discord.RawReactionActionEvent):
        if payload.user_id == self.bot.user.id:
            return

        channel = self.bot.get_channel(payload.channel_id)
        if channel is None:
            return

        message = await channel.fetch_message(payload.message_id)
        if message is None:
            return

        db = self.bot.db
        event = await db.events.find_one({"message_id": payload.message_id})
        if event is None:
            return

        emoji = payload.emoji.name
        if emoji not in ["👍", "🤷", "❌"]:
            return

        user = await self.bot.fetch_user(payload.user_id)
        user_mention = user.mention

        reactions = event.get("reactions", {})
        if user_mention not in reactions.get(emoji, []):
            reactions.setdefault(emoji, []).append(user_mention)

            await db.events.update_one(
                {"message_id": payload.message_id},
                {"$set": {"reactions": reactions}},
            )

            await self.update_event_embed(message, event, reactions)

    @commands.Cog.listener()
    async def on_raw_reaction_remove(self, payload: discord.RawReactionActionEvent):
        if payload.user_id == self.bot.user.id:
            return

        channel = self.bot.get_channel(payload.channel_id)
        if channel is None:
            return

        message = await channel.fetch_message(payload.message_id)
        if message is None:
            return

        db = self.bot.db
        event = await db.events.find_one({"message_id": payload.message_id})
        if event is None:
            return

        emoji = payload.emoji.name
        if emoji not in ["👍", "🤷", "❌"]:
            return

        user = await self.bot.fetch_user(payload.user_id)
        user_mention = user.mention

        reactions = event.get("reactions", {})
        if user_mention in reactions.get(emoji, []):
            reactions[emoji].remove(user_mention)

            await db.events.update_one(
                {"message_id": payload.message_id},
                {"$set": {"reactions": reactions}},
            )

            await self.update_event_embed(message, event, reactions)

    async def update_event_embed(
        self, message: discord.Message, event: dict, reactions: dict
    ) -> None:
        yes_users = reactions.get("👍", [])
        shrug_users = reactions.get("🤷", [])
        no_users = reactions.get("❌", [])

        yes_text = ", ".join(yes_users) if yes_users else "_žádní uživatelé_"
        shrug_text = ", ".join(shrug_users) if shrug_users else "_žádní uživatelé_"
        no_text = ", ".join(no_users) if no_users else "_žádní uživatelé_"

        embed = message.embeds[0]
        for i, field in enumerate(embed.fields):
            if field.name == "👍 Zúčastní se":
                embed.set_field_at(i, name="👍 Zúčastní se", value=yes_text)
            elif field.name == "🤷 Možná":
                embed.set_field_at(i, name="🤷 Možná", value=shrug_text)
            elif field.name == "❌ Neúčastní se":
                embed.set_field_at(i, name="❌ Neúčastní se", value=no_text)

        await message.edit(embed=embed)


async def setup(bot: BackroomsBot) -> None:
    await bot.add_cog(EventsCog(bot), guild=bot.backrooms)
