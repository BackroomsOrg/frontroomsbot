import httpx
import discord
from discord import app_commands
from discord.ext import commands
from discord.ui import Select, View, Modal, TextInput

from bot import BackroomsBot
from consts import RESERVATION_AGENT_TOKEN

RESERVATION_API_BASE_URL = "https://reservation-agent.krejzac.cz"
RESERVATION_ALLOWED_USER_IDS = [172051086071300096, 1019696733019713626]  # Padi, Pepa

MAX_USER_EVENTS = 10  # How many events to fetch for edit/cancel/select commands


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
        elif self.action == "make_reservation":
            modal = MakeReservationModal(event, self.cog)
            await interaction.response.send_modal(modal)
        elif self.action == "check_reservation_status":
            await self.cog.do_check_reservation_status(interaction, event)


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


class MakeReservationModal(Modal, title="Vytvorit rezervaci"):
    def __init__(self, event: dict, cog: "EventsCog") -> None:
        super().__init__()
        self.event = event
        self.cog = cog

        place_info = event.get("place_info") or {}
        default_business_name = place_info.get("name") or event.get("place", "")
        self.phone_number = place_info.get("phone") or ""

        self.business_name_input = TextInput(
            label="Nazev podniku",
            default=default_business_name[:100],
            required=True,
            max_length=100,
        )
        self.phone_number_input = TextInput(
            label="Volane cislo",
            default=self.phone_number[:100],
            required=False,
            max_length=100,
        )
        self.reservation_time_input = TextInput(
            label="Cas rezervace",
            placeholder="Napriklad: 2026-02-14 19:00",
            required=True,
            max_length=100,
        )
        self.num_people_input = TextInput(
            label="Pocet lidi",
            placeholder="Napriklad: 4",
            required=True,
            max_length=10,
        )
        self.person_name_input = TextInput(
            label="Jmeno osoby",
            required=True,
            placeholder="Napriklad: Roman Janota",
            max_length=100,
        )

        self.add_item(self.business_name_input)
        self.add_item(self.reservation_time_input)
        self.add_item(self.num_people_input)
        self.add_item(self.person_name_input)
        self.add_item(self.phone_number_input)

    async def on_submit(self, interaction: discord.Interaction) -> None:
        await self.cog.do_make_reservation(
            interaction=interaction,
            event=self.event,
            business_name=self.business_name_input.value,
            phone_number=self.phone_number_input.value,
            reservation_time=self.reservation_time_input.value,
            num_people=self.num_people_input.value,
            person_name=self.person_name_input.value,
        )


class EventsCog(commands.Cog):
    def __init__(self, bot: BackroomsBot) -> None:
        self.bot = bot

    async def get_user_events(
        self, user_id: int, limit: int = MAX_USER_EVENTS
    ) -> list[dict]:
        db = self.bot.db
        cursor = db.events.find({"creator_id": user_id}).sort("_id", -1).limit(limit)
        return await cursor.to_list(length=limit)

    def _build_transcript_lines(self, transcript: list[dict]) -> list[str]:
        lines = []
        for turn in transcript:
            role = turn.get("role")
            message = (turn.get("message") or "").strip()
            if not message:
                continue

            if role == "agent":
                speaker = "🤖 Agent"
            elif role == "user":
                speaker = "👤 Person"
            else:
                speaker = "ℹ️ Other"

            lines.append(f"{speaker}: {message}")
        return lines

    def _chunk_lines(self, lines: list[str], max_chars: int = 3500) -> list[str]:
        if not lines:
            return []

        chunks = []
        current = lines[0]
        for line in lines[1:]:
            candidate = f"{current}\n\n{line}"
            if len(candidate) > max_chars:
                chunks.append(current)
                current = line
            else:
                current = candidate
        chunks.append(current)
        return chunks

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
        embed.add_field(
            name="👍 Zúčastní se (0)", value="_žádní uživatelé_", inline=False
        )
        embed.add_field(name="🤷 Možná (0)", value="_žádní uživatelé_", inline=False)
        embed.add_field(
            name="❌ Neúčastní se (0)", value="_žádní uživatelé_", inline=False
        )

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
        await message.add_reaction("📌")

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

    async def do_get_place(self, interaction: discord.Interaction, event: dict) -> None:
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
                    f"{RESERVATION_API_BASE_URL}/research_business",
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
            await interaction.followup.send("Event nemá embed.", ephemeral=True)
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
                            i,
                            name="ℹ️ Popis",
                            value=data["description"][:1024],
                            inline=False,
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

    @app_commands.command(
        name="make_reservation",
        description="Create reservation call for your event",
    )
    async def make_reservation(self, interaction: discord.Interaction) -> None:
        if interaction.user.id not in RESERVATION_ALLOWED_USER_IDS:
            await interaction.response.send_message(
                "Na tento prikaz nemas opravneni.",
                ephemeral=True,
            )
            return

        events = await self.get_user_events(interaction.user.id)
        eligible_events = [
            event for event in events if (event.get("place_info") or {}).get("phone")
        ]
        if not eligible_events:
            await interaction.response.send_message(
                "Nenalezeny zadne eventy s telefonem. Nejdriv spust /event_get_place nebo telefon dopln v /edit_event.",
                ephemeral=True,
            )
            return

        view = EventSelectView(
            eligible_events, "make_reservation", self, interaction.user.id
        )
        await interaction.response.send_message(
            "Vyber event pro rezervaci:",
            view=view,
            ephemeral=True,
        )

    async def do_make_reservation(
        self,
        interaction: discord.Interaction,
        event: dict,
        business_name: str,
        phone_number: str,
        reservation_time: str,
        num_people: str,
        person_name: str,
    ) -> None:
        if interaction.user.id not in RESERVATION_ALLOWED_USER_IDS:
            await interaction.response.send_message(
                "Na tento prikaz nemas opravneni.",
                ephemeral=True,
            )
            return

        event_phone_number = (event.get("place_info") or {}).get("phone")
        effective_phone_number = phone_number.strip() or event_phone_number
        if not effective_phone_number:
            await interaction.response.send_message(
                "Vybrany event nema telefon. Nejdriv dopln telefon nebo spust /event_get_place.",
                ephemeral=True,
            )
            return

        await interaction.response.defer(ephemeral=True)
        public_embed = discord.Embed(
            title="📞 Bot dělá rezervaci",
            color=discord.Color.orange(),
        )
        public_embed.add_field(
            name="Event",
            value=event.get("name", "Neznámý event"),
            inline=False,
        )
        public_embed.add_field(name="Podnik", value=business_name, inline=True)
        public_embed.add_field(
            name="Telefon", value=effective_phone_number, inline=True
        )
        public_embed.add_field(name="Čas", value=reservation_time, inline=True)
        public_embed.add_field(name="Počet lidí", value=num_people, inline=True)
        public_embed.add_field(name="Jméno", value=person_name, inline=True)
        await interaction.followup.send(embed=public_embed, ephemeral=False)

        payload = {
            "businessName": business_name,
            "phoneNumber": effective_phone_number,
            "reservationTime": reservation_time,
            "numPeople": num_people,
            "personName": person_name,
        }

        try:
            async with httpx.AsyncClient(timeout=30) as client:
                response = await client.post(
                    f"{RESERVATION_API_BASE_URL}/make_reservation",
                    json=payload,
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
                f"Reservation API vratilo chybu: {e.response.status_code}",
                ephemeral=True,
            )
            return
        except Exception as e:
            await interaction.followup.send(
                f"Nepodarilo se vytvorit rezervaci: {e}",
                ephemeral=True,
            )
            return

        db = self.bot.db
        await db.events.update_one(
            {"message_id": event["message_id"]},
            {
                "$set": {
                    "reservation.success": data.get("success"),
                    "reservation.message": data.get("message"),
                    "reservation.conversationId": data.get("conversationId"),
                    "reservation.callSid": data.get("callSid"),
                    "reservation.request": payload,
                }
            },
        )

        conversation_id = data.get("conversationId", "n/a")
        call_sid = data.get("callSid", "n/a")
        await interaction.followup.send(
            f"Rezervace odeslana.\nconversationId: `{conversation_id}`\ncallSid: `{call_sid}`",
            ephemeral=True,
        )

    @app_commands.command(
        name="check_reservation_status",
        description="Check reservation call status and transcript",
    )
    async def check_reservation_status(self, interaction: discord.Interaction) -> None:
        if interaction.user.id not in RESERVATION_ALLOWED_USER_IDS:
            await interaction.response.send_message(
                "Na tento prikaz nemas opravneni.",
                ephemeral=True,
            )
            return

        events = await self.get_user_events(interaction.user.id)
        eligible_events = [
            event
            for event in events
            if (event.get("reservation") or {}).get("conversationId")
        ]
        if not eligible_events:
            await interaction.response.send_message(
                "Nenalezeny zadne eventy s conversationId. Nejdriv spust /make_reservation.",
                ephemeral=True,
            )
            return

        view = EventSelectView(
            eligible_events, "check_reservation_status", self, interaction.user.id
        )
        await interaction.response.send_message(
            "Vyber event pro kontrolu stavu rezervace:",
            view=view,
            ephemeral=True,
        )

    async def do_check_reservation_status(
        self, interaction: discord.Interaction, event: dict
    ) -> None:
        if interaction.user.id not in RESERVATION_ALLOWED_USER_IDS:
            await interaction.response.send_message(
                "Na tento prikaz nemas opravneni.",
                ephemeral=True,
            )
            return

        reservation = event.get("reservation") or {}
        conversation_id = reservation.get("conversationId")
        if not conversation_id:
            await interaction.response.send_message(
                "U eventu chybi conversationId. Nejdriv spust /make_reservation.",
                ephemeral=True,
            )
            return

        await interaction.response.defer(ephemeral=True)

        try:
            async with httpx.AsyncClient(timeout=30) as client:
                response = await client.get(
                    f"{RESERVATION_API_BASE_URL}/conversation_details/{conversation_id}",
                    headers={
                        "Accept": "*/*",
                        "x-magic": RESERVATION_AGENT_TOKEN or "",
                    },
                )
                response.raise_for_status()
                data = response.json()
        except httpx.HTTPStatusError as e:
            await interaction.followup.send(
                f"Conversation API vratilo chybu: {e.response.status_code}",
                ephemeral=True,
            )
            return
        except Exception as e:
            await interaction.followup.send(
                f"Nepodarilo se nacist status rezervace: {e}",
                ephemeral=True,
            )
            return

        status = data.get("status", "unknown")
        analysis = data.get("analysis") or {}
        metadata = data.get("metadata") or {}
        phone_call = metadata.get("phoneCall") or {}
        transcript = data.get("transcript") or []
        transcript_lines = self._build_transcript_lines(transcript)
        transcript_chunks = self._chunk_lines(transcript_lines)

        status_embed = discord.Embed(
            title=f"Status rezervace: {event.get('name', 'Event')}",
            color=discord.Color.blurple(),
        )
        status_embed.add_field(name="Status", value=status, inline=True)
        status_embed.add_field(
            name="Uspesnost",
            value=analysis.get("callSuccessful", "unknown"),
            inline=True,
        )
        status_embed.add_field(
            name="conversationId",
            value=data.get("conversationId", conversation_id),
            inline=False,
        )
        status_embed.add_field(
            name="callSid",
            value=phone_call.get("callSid", reservation.get("callSid", "n/a")),
            inline=False,
        )
        status_embed.add_field(
            name="Delka hovoru",
            value=str(metadata.get("callDurationSecs", "n/a")),
            inline=True,
        )
        status_embed.add_field(
            name="Volane cislo",
            value=phone_call.get("externalNumber", "n/a"),
            inline=True,
        )

        call_summary_title = analysis.get("callSummaryTitle")
        transcript_summary = analysis.get("transcriptSummary")
        if call_summary_title:
            status_embed.add_field(
                name="Souhrn",
                value=call_summary_title[:1024],
                inline=False,
            )
        if transcript_summary:
            status_embed.add_field(
                name="Shrnuti hovoru",
                value=transcript_summary[:1024],
                inline=False,
            )

        transcript_embeds = []
        total_chunks = len(transcript_chunks)
        for idx, chunk in enumerate(transcript_chunks, start=1):
            transcript_embed = discord.Embed(
                title=f"Prepis hovoru {idx}/{total_chunks}",
                description=chunk,
                color=discord.Color.dark_teal(),
            )
            transcript_embeds.append(transcript_embed)

        db = self.bot.db
        await db.events.update_one(
            {"message_id": event["message_id"]},
            {
                "$set": {
                    "reservation.statusCheck.status": status,
                    "reservation.statusCheck.callSuccessful": analysis.get(
                        "callSuccessful"
                    ),
                    "reservation.statusCheck.callSummaryTitle": call_summary_title,
                    "reservation.statusCheck.transcriptSummary": transcript_summary,
                    "reservation.statusCheck.callDurationSecs": metadata.get(
                        "callDurationSecs"
                    ),
                    "reservation.statusCheck.terminationReason": metadata.get(
                        "terminationReason"
                    ),
                    "reservation.statusCheck.externalNumber": phone_call.get(
                        "externalNumber"
                    ),
                    "reservation.statusCheck.callSid": phone_call.get("callSid"),
                    "reservation.statusCheck.transcript": transcript,
                }
            },
        )

        channel = self.bot.get_channel(event.get("channel_id"))
        if channel is not None:
            try:
                message = await channel.fetch_message(event["message_id"])
                if message and message.embeds:
                    event_embed = message.embeds[0]
                    reservation_value = (
                        f"Status: {status}\n"
                        f"callSid: {phone_call.get('callSid', reservation.get('callSid', 'n/a'))}"
                    )
                    field_names = [field.name for field in event_embed.fields]
                    if "📞 Rezervace" in field_names:
                        for i, field in enumerate(event_embed.fields):
                            if field.name == "📞 Rezervace":
                                event_embed.set_field_at(
                                    i,
                                    name="📞 Rezervace",
                                    value=reservation_value[:1024],
                                    inline=False,
                                )
                                break
                    else:
                        event_embed.add_field(
                            name="📞 Rezervace",
                            value=reservation_value[:1024],
                            inline=False,
                        )
                    await message.edit(embed=event_embed)
            except Exception:
                pass

        embeds_to_send = [status_embed, *transcript_embeds]
        for i in range(0, len(embeds_to_send), 10):
            await interaction.followup.send(
                embeds=embeds_to_send[i : i + 10],
                ephemeral=False,
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
        if emoji == "📌":
            if payload.user_id == event.get("creator_id") and not message.pinned:
                await message.pin(reason="Event pinned by creator via reaction.")
                return

            user = payload.member or await self.bot.fetch_user(payload.user_id)
            await message.remove_reaction(payload.emoji, user)
            return

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

        yes_count = len(yes_users)
        shrug_count = len(shrug_users)
        no_count = len(no_users)

        embed = message.embeds[0]
        for i, field in enumerate(embed.fields):
            if field.name.startswith("👍 Zúčastní se"):
                embed.set_field_at(
                    i,
                    name=f"👍 Zúčastní se ({yes_count})",
                    value=yes_text,
                )
            elif field.name.startswith("🤷 Možná"):
                embed.set_field_at(
                    i,
                    name=f"🤷 Možná ({shrug_count})",
                    value=shrug_text,
                )
            elif field.name.startswith("❌ Neúčastní se"):
                embed.set_field_at(
                    i,
                    name=f"❌ Neúčastní se ({no_count})",
                    value=no_text,
                )

        await message.edit(embed=embed)


async def setup(bot: BackroomsBot) -> None:
    await bot.add_cog(EventsCog(bot), guild=bot.backrooms)
