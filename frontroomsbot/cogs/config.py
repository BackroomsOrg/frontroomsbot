from typing import Callable, Any, Union, Awaitable, overload
from bot import BackroomsBot
from discord.ext import commands
from discord import app_commands, Interaction, TextStyle, AllowedMentions
import discord.ui as ui
import asyncio

_NO_VALUE = object()


class Cfg:
    def __init__(
        self, t: Callable[[Any], Any], default=_NO_VALUE, description: str = ""
    ) -> None:
        self.name: str
        self.t = t
        self.default = default
        self.description = description

    def convert(self, value):
        return self.t(value)

    async def get(self, obj):
        if self.default is _NO_VALUE:
            return self.convert((await obj._cfg())[self.name])
        else:
            if (value := (await obj._cfg()).get(self.name, _NO_VALUE)) is _NO_VALUE:
                return self.default
            else:
                return self.convert(value)

    @property
    def label(self):
        return self.description or self.name

    def __set_name__(self, owner, name):
        owner.options = getattr(owner, "options", []) + [self]
        self.name = name

    @overload
    def __get__(self, obj: None, objtype=None) -> "Cfg":
        ...

    @overload
    def __get__(self, obj: "ConfigCog", objtype=None) -> Awaitable[Any]:
        ...

    def __get__(self, obj: Union["ConfigCog", None], objtype=None) -> "Cfg" | Awaitable[Any]:
        if obj is None:
            return self
        else:
            return self.get(obj)

    def __set__(self, obj, v, objtype=None):
        raise RuntimeError("cannot set config value")


class ConfigCog(commands.Cog):
    key: str
    options: list[Cfg]

    def __init__(self, bot: BackroomsBot):
        self.bot = bot
        self.config = bot.db.config

    async def _cfg(self) -> dict[Any, Any]:
        return await self.config.find_one({"key": self.key}) or {}

    def __init_subclass__(cls) -> None:
        cls.key = cls.__module__


async def gen_modal(t: str, items: list[Cfg], inst: ConfigCog) -> ui.Modal:
    fields: dict[str, ui.TextInput] = {}
    for item in items:
        # TODO better picking of fields here
        try:
            value = str(await item.get(inst))
        except KeyError:
            value = None
        fields[item.name] = ui.TextInput(
            label=item.label,
            default=value,
            required=False,
        )

    async def on_submit(self, interaction: Interaction):
        errors = []
        new_data: Any = {'key': inst.__module__}
        for item in items:
            raw_value = getattr(self, item.name).value
            # discord seems to offer up '' instead of None when a field is left unset
            if not raw_value:
                continue
            try:
                value = item.convert(raw_value)
            except Exception:
                errors.append((item, raw_value))
            else:
                try:
                    old_value = await item.get(inst)
                except KeyError:
                    new_data[item.name] = value
                else:
                    if value != old_value:
                        new_data[item.name] = value
        if errors:
            error_msg = [f"`{item.name}={v!r}`" for item, v in errors]
            await interaction.response.send_message(
                "Failed to assign some values:\n" + "\n".join(error_msg),
                allowed_mentions=AllowedMentions.none(),
            )
        elif len(new_data) > 1: # more than just key: module
            changes = [f"`{k}={v!r}`" for k, v in new_data.items()]
            send = interaction.response.send_message(
                "Updating with new values:\n" + "\n".join(changes),
                allowed_mentions=AllowedMentions.none(),
            )
            db = inst.config.update_one({"key": inst.__module__}, {'$set':new_data}, upsert=True)
            await asyncio.gather(send, db)
        else:
            await interaction.response.send_message('No changes were made', ephemeral=True)

    methods = dict(on_submit=on_submit)
    return type("CogModal", (ui.Modal,), fields | methods, title="Configure " + t)()  # type: ignore


class ConfigCommands(commands.Cog):
    def __init__(self, bot: BackroomsBot) -> None:
        self.bot = bot

    async def cog_autocomplete(self, interaction: Interaction, current: str):
        cogs = ConfigCog.__subclasses__()
        return [
            app_commands.Choice(name=cog.key, value=cog.key)
            for cog in cogs
            if current in cog.key
        ]

    @app_commands.command(name="config", description="Configure a specific cog")
    @app_commands.autocomplete(cog_module=cog_autocomplete)
    async def get(self, interaction: Interaction, cog_module: str):
        """/config"""
        cogs = ConfigCog.__subclasses__()
        try:
            cog = next(cog for cog in cogs if cog.key == cog_module)
        except StopIteration:
            await interaction.response.send_message(
                f"No such configurable cog.", ephemeral=True
            )
        else:
            cog_instance = self.bot.get_cog(cog.__cog_name__)
            if not cog_instance:
                await interaction.response.send_message(
                    f"That cog is not loaded", ephemeral=True
                )
            assert isinstance(
                cog_instance, ConfigCog
            ), "Found a non-configurable cog, perhaps two cogs live in the same module"
            await interaction.response.send_modal(
                await gen_modal(cog_module, cog.options, cog_instance)
            )


async def setup(bot):
    await bot.add_cog(ConfigCommands(bot), guild=bot.guilds[0])
