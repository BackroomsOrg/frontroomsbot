import sys  # noqa: E402
from pathlib import Path  # noqa: E402
from unittest.mock import AsyncMock, MagicMock  # noqa: E402

import pytest  # noqa: E402

sys.path.insert(0, str(Path(__file__).parent.parent / "frontroomsbot"))  # noqa: E402

from cogs.events import EventsCog, setup  # noqa: E402


@pytest.fixture
def mock_bot():
    bot = MagicMock()
    bot.backrooms = MagicMock()
    bot.db = MagicMock()
    return bot


@pytest.fixture
def events_cog(mock_bot):
    return EventsCog(mock_bot)


@pytest.mark.asyncio
async def test_events_cog_initialization(mock_bot):
    cog = EventsCog(mock_bot)
    assert cog.bot == mock_bot


@pytest.mark.asyncio
async def test_create_event(events_cog):
    interaction = MagicMock()
    interaction.user.mention = "<@testuser>"
    interaction.user.display_name = "TestUser"

    mock_message = AsyncMock()
    mock_message.id = 12345
    mock_message.channel.id = 67890
    interaction.response.send_message = AsyncMock()
    interaction.original_response = AsyncMock(return_value=mock_message)

    await events_cog.create_event.callback(
        events_cog, interaction, place="Test Place", date="2026-02-15 20:00"
    )

    interaction.response.send_message.assert_called_once()
    call_args = interaction.response.send_message.call_args
    embed = call_args.kwargs.get("embed") or call_args[1].get("embed")
    assert embed is not None
    assert embed.title == "Nová událost"
    assert "Test Place" in embed.description
    assert len(embed.fields) == 4
    assert embed.fields[2].name == "👍 Zúčastní se"
    assert embed.fields[3].name == "🤷 Možná"

    mock_message.add_reaction.assert_any_call("👍")
    mock_message.add_reaction.assert_any_call("🤷")

    events_cog.bot.db.events.insert_one.assert_called_once()


@pytest.mark.asyncio
async def test_on_raw_reaction_add_non_event_message(events_cog):
    events_cog.bot.db.events.find_one = AsyncMock(return_value=None)
    payload = MagicMock()
    payload.message_id = 99999
    payload.user_id = 123
    payload.emoji.name = "👍"
    payload.channel_id = 67890

    channel = MagicMock()
    channel.fetch_message = AsyncMock()
    events_cog.bot.get_channel = MagicMock(return_value=channel)

    await events_cog.on_raw_reaction_add(payload)

    events_cog.bot.db.events.find_one.assert_called_once_with({"message_id": 99999})


@pytest.mark.asyncio
async def test_on_raw_reaction_add_updates_embed(events_cog):
    events_cog.bot.db.events.find_one = AsyncMock(
        return_value={
            "message_id": 12345,
            "reactions": {"👍": [], "🤷": []},
        }
    )
    events_cog.bot.db.events.update_one = AsyncMock()

    payload = MagicMock()
    payload.message_id = 12345
    payload.user_id = 456
    payload.emoji.name = "👍"
    payload.channel_id = 67890

    channel = MagicMock()
    message = MagicMock()
    message.embeds = [MagicMock()]
    message.embeds[0].fields = [
        MagicMock(name="📅 Datum", value="2026-02-15"),
        MagicMock(name="👤 Vytvořil", value="<@creator>"),
        MagicMock(name="👍 Zúčastní se", value="_žádní uživatelé_"),
        MagicMock(name="🤷 Možná", value="_žádní uživatelé_"),
    ]
    channel.fetch_message = AsyncMock(return_value=message)
    events_cog.bot.get_channel = MagicMock(return_value=channel)

    user = MagicMock()
    user.mention = "<@reactionuser>"
    events_cog.bot.fetch_user = AsyncMock(return_value=user)

    await events_cog.on_raw_reaction_add(payload)

    events_cog.bot.db.events.update_one.assert_called_once()


@pytest.mark.asyncio
async def test_on_raw_reaction_remove(events_cog):
    events_cog.bot.db.events.find_one = AsyncMock(
        return_value={
            "message_id": 12345,
            "reactions": {"👍": ["<@user1>"], "🤷": []},
        }
    )
    events_cog.bot.db.events.update_one = AsyncMock()

    payload = MagicMock()
    payload.message_id = 12345
    payload.user_id = 123
    payload.emoji.name = "👍"
    payload.channel_id = 67890

    channel = MagicMock()
    message = MagicMock()
    message.embeds = [MagicMock()]
    message.embeds[0].fields = [
        MagicMock(name="📅 Datum", value="2026-02-15"),
        MagicMock(name="👤 Vytvořil", value="<@creator>"),
        MagicMock(name="👍 Zúčastní se", value="<@user1>"),
        MagicMock(name="🤷 Možná", value="_žádní uživatelé_"),
    ]
    channel.fetch_message = AsyncMock(return_value=message)
    events_cog.bot.get_channel = MagicMock(return_value=channel)

    user = MagicMock()
    user.mention = "<@user1>"
    events_cog.bot.fetch_user = AsyncMock(return_value=user)

    await events_cog.on_raw_reaction_remove(payload)

    events_cog.bot.db.events.update_one.assert_called_once()


@pytest.mark.asyncio
async def test_on_member_remove(events_cog):
    member = MagicMock()
    member.name = "TestUser"

    result = await events_cog.on_member_remove(member)
    assert result is None


@pytest.mark.asyncio
async def test_on_message_delete(events_cog):
    message = MagicMock()
    message.content = "Test message"
    message.author = MagicMock()

    result = await events_cog.on_message_delete(message)
    assert result is None


@pytest.mark.asyncio
async def test_on_message_edit(events_cog):
    before = MagicMock()
    before.content = "Original message"
    after = MagicMock()
    after.content = "Edited message"

    result = await events_cog.on_message_edit(before, after)
    assert result is None


@pytest.mark.asyncio
async def test_setup(mock_bot):
    mock_bot.add_cog = AsyncMock()
    await setup(mock_bot)
    mock_bot.add_cog.assert_called_once()

    call_args = mock_bot.add_cog.call_args
    assert isinstance(call_args[0][0], EventsCog)
    assert call_args[1].get("guild") == mock_bot.backrooms


@pytest.mark.asyncio
async def test_edit_event_invalid_message_id(events_cog):
    interaction = MagicMock()
    interaction.user.id = 123
    interaction.response.send_message = AsyncMock()

    await events_cog.edit_event(
        events_cog, interaction, message_id="invalid", place="New Place"
    )

    interaction.response.send_message.assert_called_once()
    call_args = interaction.response.send_message.call_args
    assert "Invalid message ID" in str(call_args)


@pytest.mark.asyncio
async def test_edit_event_not_found(events_cog):
    events_cog.bot.db.events.find_one = AsyncMock(return_value=None)

    interaction = MagicMock()
    interaction.user.id = 123
    interaction.response.send_message = AsyncMock()

    await events_cog.edit_event(
        events_cog, interaction, message_id="12345", place="New Place"
    )

    events_cog.bot.db.events.find_one.assert_called_once_with({"message_id": 12345})
    interaction.response.send_message.assert_called_once()
    call_args = interaction.response.send_message.call_args
    assert "not found" in str(call_args).lower()


@pytest.mark.asyncio
async def test_edit_event_not_creator(events_cog):
    events_cog.bot.db.events.find_one = AsyncMock(
        return_value={"message_id": 12345, "creator_id": 999, "channel_id": 67890}
    )

    interaction = MagicMock()
    interaction.user.id = 123
    interaction.response.send_message = AsyncMock()

    await events_cog.edit_event(
        events_cog, interaction, message_id="12345", place="New Place"
    )

    interaction.response.send_message.assert_called_once()
    call_args = interaction.response.send_message.call_args
    assert "only edit events that you created" in str(call_args).lower()


@pytest.mark.asyncio
async def test_edit_event_no_fields(events_cog):
    events_cog.bot.db.events.find_one = AsyncMock(
        return_value={"message_id": 12345, "creator_id": 123, "channel_id": 67890}
    )

    interaction = MagicMock()
    interaction.user.id = 123
    interaction.response.send_message = AsyncMock()

    await events_cog.edit_event(events_cog, interaction, message_id="12345")

    interaction.response.send_message.assert_called_once()
    call_args = interaction.response.send_message.call_args
    assert "at least one field" in str(call_args).lower()


@pytest.mark.asyncio
async def test_edit_event_success_place_only(events_cog):
    events_cog.bot.db.events.find_one = AsyncMock(
        return_value={
            "message_id": 12345,
            "creator_id": 123,
            "channel_id": 67890,
            "place": "Old Place",
            "date": "2026-02-15",
        }
    )
    events_cog.bot.db.events.update_one = AsyncMock()

    interaction = MagicMock()
    interaction.user.id = 123
    interaction.response.send_message = AsyncMock()

    channel = MagicMock()
    message = MagicMock()
    message.embeds = [MagicMock()]
    message.embeds[0].description = "**Old Place**"
    message.embeds[0].fields = [
        MagicMock(name="📅 Datum", value="2026-02-15"),
        MagicMock(name="👤 Vytvořil", value="<@creator>"),
        MagicMock(name="👍 Zúčastní se", value="_žádní uživatelé_"),
        MagicMock(name="🤷 Možná", value="_žádní uživatelé_"),
    ]
    channel.fetch_message = AsyncMock(return_value=message)
    events_cog.bot.get_channel = MagicMock(return_value=channel)

    await events_cog.edit_event(
        events_cog, interaction, message_id="12345", place="New Place"
    )

    events_cog.bot.db.events.update_one.assert_called_once()
    interaction.response.send_message.assert_called_once()


@pytest.mark.asyncio
async def test_edit_event_success_date_only(events_cog):
    events_cog.bot.db.events.find_one = AsyncMock(
        return_value={
            "message_id": 12345,
            "creator_id": 123,
            "channel_id": 67890,
            "place": "Some Place",
            "date": "2026-02-15",
        }
    )
    events_cog.bot.db.events.update_one = AsyncMock()

    interaction = MagicMock()
    interaction.user.id = 123
    interaction.response.send_message = AsyncMock()

    channel = MagicMock()
    message = MagicMock()
    message.embeds = [MagicMock()]
    message.embeds[0].description = "**Some Place**"
    message.embeds[0].fields = [
        MagicMock(name="📅 Datum", value="2026-02-15"),
        MagicMock(name="👤 Vytvořil", value="<@creator>"),
        MagicMock(name="👍 Zúčastní se", value="_žádní uživatelé_"),
        MagicMock(name="🤷 Možná", value="_žádní uživatelé_"),
    ]
    channel.fetch_message = AsyncMock(return_value=message)
    events_cog.bot.get_channel = MagicMock(return_value=channel)

    await events_cog.edit_event(
        events_cog, interaction, message_id="12345", date="2026-03-01 18:00"
    )

    events_cog.bot.db.events.update_one.assert_called_once()
    interaction.response.send_message.assert_called_once()
