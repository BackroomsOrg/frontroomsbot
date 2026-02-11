import sys  # noqa: E402
from pathlib import Path  # noqa: E402
from unittest.mock import AsyncMock, MagicMock, patch  # noqa: E402
from datetime import datetime, timedelta  # noqa: E402
from bson import ObjectId  # noqa: E402

import pytest  # noqa: E402

sys.path.insert(0, str(Path(__file__).parent.parent / "frontroomsbot"))  # noqa: E402

from cogs.event_manager import EventManagerCog, setup  # noqa: E402


@pytest.fixture
def mock_bot():
    bot = MagicMock()
    bot.backrooms = MagicMock()
    bot.db = MagicMock()
    bot.db.events = MagicMock()
    return bot


@pytest.fixture
def event_cog(mock_bot):
    return EventManagerCog(mock_bot)


@pytest.fixture
def mock_interaction():
    interaction = AsyncMock()
    interaction.user = MagicMock()
    interaction.user.id = 123456789
    interaction.user.display_name = "TestUser"
    interaction.user.mention = "@TestUser"
    interaction.channel_id = 987654321
    interaction.guild_id = 111111111
    return interaction


@pytest.mark.asyncio
async def test_event_manager_cog_initialization(mock_bot):
    cog = EventManagerCog(mock_bot)
    assert cog.bot == mock_bot


@pytest.mark.asyncio
async def test_create_event_success(event_cog, mock_interaction):
    future_date = (datetime.now() + timedelta(days=1)).strftime("%Y-%m-%d %H:%M")

    mock_result = MagicMock()
    mock_result.inserted_id = "mock_event_id_123"
    event_cog.bot.db.events.insert_one = AsyncMock(return_value=mock_result)

    await event_cog.create_event.callback(
        event_cog,
        interaction=mock_interaction,
        name="Test Event",
        date=future_date,
        place="Test Place",
        description="Test Description",
    )

    event_cog.bot.db.events.insert_one.assert_called_once()
    call_args = event_cog.bot.db.events.insert_one.call_args[0][0]
    assert call_args["name"] == "Test Event"
    assert call_args["place"] == "Test Place"
    assert call_args["description"] == "Test Description"
    assert call_args["creator_id"] == 123456789
    assert call_args["creator_name"] == "TestUser"

    mock_interaction.response.send_message.assert_called_once()


@pytest.mark.asyncio
async def test_create_event_invalid_date_format(event_cog, mock_interaction):
    await event_cog.create_event.callback(
        event_cog,
        interaction=mock_interaction,
        name="Test Event",
        date="invalid-date",
        place="Test Place",
        description="Test Description",
    )

    event_cog.bot.db.events.insert_one.assert_not_called()
    mock_interaction.response.send_message.assert_called_once()
    call_args = mock_interaction.response.send_message.call_args
    assert "Invalid date format" in call_args[0][0]
    assert call_args[1]["ephemeral"] is True


@pytest.mark.asyncio
async def test_create_event_past_date(event_cog, mock_interaction):
    past_date = (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d %H:%M")

    await event_cog.create_event.callback(
        event_cog,
        interaction=mock_interaction,
        name="Test Event",
        date=past_date,
        place="Test Place",
        description="Test Description",
    )

    event_cog.bot.db.events.insert_one.assert_not_called()
    mock_interaction.response.send_message.assert_called_once()
    call_args = mock_interaction.response.send_message.call_args
    assert "must be in the future" in call_args[0][0]
    assert call_args[1]["ephemeral"] is True


@pytest.mark.asyncio
async def test_create_event_no_description(event_cog, mock_interaction):
    future_date = (datetime.now() + timedelta(days=1)).strftime("%Y-%m-%d %H:%M")

    mock_result = MagicMock()
    mock_result.inserted_id = "mock_event_id_456"
    event_cog.bot.db.events.insert_one = AsyncMock(return_value=mock_result)

    await event_cog.create_event.callback(
        event_cog,
        interaction=mock_interaction,
        name="Test Event No Desc",
        date=future_date,
        place="Test Place",
        description=None,
    )

    event_cog.bot.db.events.insert_one.assert_called_once()
    call_args = event_cog.bot.db.events.insert_one.call_args[0][0]
    assert call_args["name"] == "Test Event No Desc"
    assert call_args["place"] == "Test Place"
    assert call_args["description"] == ""

    mock_interaction.response.send_message.assert_called_once()


@pytest.mark.asyncio
async def test_setup(mock_bot):
    with patch.object(mock_bot, "add_cog", new_callable=AsyncMock) as mock_add_cog:
        await setup(mock_bot)
        mock_add_cog.assert_called_once()

        call_args = mock_add_cog.call_args
        assert isinstance(call_args[0][0], EventManagerCog)
        assert call_args[1]["guild"] == mock_bot.backrooms


@pytest.mark.asyncio
async def test_cancel_event_invalid_id_format(event_cog, mock_interaction):
    event_cog.bot.db.events.find_one = AsyncMock()

    await event_cog.cancel_event.callback(
        event_cog, interaction=mock_interaction, event_id="invalid-id"
    )

    event_cog.bot.db.events.find_one.assert_not_called()
    mock_interaction.response.send_message.assert_called_once()
    call_args = mock_interaction.response.send_message.call_args
    assert "Invalid event ID format" in call_args[0][0]
    assert call_args[1]["ephemeral"] is True


@pytest.mark.asyncio
async def test_cancel_event_not_found(event_cog, mock_interaction):
    event_cog.bot.db.events.find_one = AsyncMock(return_value=None)

    valid_id = str(ObjectId())
    await event_cog.cancel_event.callback(
        event_cog, interaction=mock_interaction, event_id=valid_id
    )

    event_cog.bot.db.events.find_one.assert_called_once_with(
        {"_id": ObjectId(valid_id)}
    )
    mock_interaction.response.send_message.assert_called_once()
    call_args = mock_interaction.response.send_message.call_args
    assert "not found" in call_args[0][0].lower()
    assert call_args[1]["ephemeral"] is True


@pytest.mark.asyncio
async def test_cancel_event_not_creator(event_cog, mock_interaction):
    event_cog.bot.db.events.find_one = AsyncMock(
        return_value={
            "_id": ObjectId(),
            "name": "Test Event",
            "creator_id": 999999999,
            "place": "Test Place",
            "date": datetime.now() + timedelta(days=1),
        }
    )
    event_cog.bot.db.events.delete_one = AsyncMock()

    valid_id = str(ObjectId())
    await event_cog.cancel_event.callback(
        event_cog, interaction=mock_interaction, event_id=valid_id
    )

    event_cog.bot.db.events.delete_one.assert_not_called()
    mock_interaction.response.send_message.assert_called_once()
    call_args = mock_interaction.response.send_message.call_args
    assert "only cancel events that you created" in call_args[0][0].lower()
    assert call_args[1]["ephemeral"] is True


@pytest.mark.asyncio
async def test_cancel_event_success(event_cog, mock_interaction):
    event_date = datetime.now() + timedelta(days=1)
    event_cog.bot.db.events.find_one = AsyncMock(
        return_value={
            "_id": ObjectId(),
            "name": "Test Event to Cancel",
            "creator_id": mock_interaction.user.id,
            "place": "Test Place",
            "date": event_date,
        }
    )
    event_cog.bot.db.events.delete_one = AsyncMock()

    valid_id = str(ObjectId())
    await event_cog.cancel_event.callback(
        event_cog, interaction=mock_interaction, event_id=valid_id
    )

    event_cog.bot.db.events.delete_one.assert_called_once()
    call_args = event_cog.bot.db.events.delete_one.call_args
    assert call_args[0][0] == {"_id": ObjectId(valid_id)}

    mock_interaction.response.send_message.assert_called_once()
    call_args = mock_interaction.response.send_message.call_args
    embed = call_args[1]["embed"]
    assert embed.title == "Event Cancelled"
    assert "Test Event to Cancel" in embed.description
