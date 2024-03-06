from typing import Callable, Any, Union, Awaitable, overload
from bot import BackroomsBot
from discord.ext import commands
from discord import Interaction, AllowedMentions
import discord.ui as ui
import asyncio
from contextlib import suppress
import motor.motor_asyncio as maio
import pymongo.errors

_NO_VALUE = object()

_CACHE: dict[str, Any] = {}
_UNLOADED_COGS: dict[str, "ConfigCog"] = {}


def get_unloaded_cog(key: str) -> "ConfigCog":
    return _UNLOADED_COGS[key]


def clear_cache():
    _CACHE.clear()


async def _cached_get(col: maio.AsyncIOMotorCollection, key: str) -> dict[str, Any]:
    """
    Load a cogs configuration, or find it in the cache if it is present there
    """
    try:
        return _CACHE[key]
    except KeyError:
        result = await col.find_one({"key": key}) or {}
        _CACHE[key] = result
        return result


async def _cached_update(
    col: maio.AsyncIOMotorCollection, key: str, values: dict[str, Any]
):
    """
    Update a cogs configuration, invalidating its cache entry.

    The parameter values must include the key as well
    """
    with suppress(KeyError):
        # leave the race condition to mongodb
        del _CACHE[key]
    await col.update_one({"key": key}, {"$set": values}, upsert=True)


class Cfg:
    def __init__(
        self, t: Callable[[Any], Any], default=_NO_VALUE, description: str = ""
    ) -> None:
        """
        A configuration option for a ConfigCog. A descriptor that provides an **awaitable** returning the configuration value at that point.

        t is the function that parses and validates the config value to string - generally str or int. Make sure that `t(str(v)) == v`, and that `motor` will accept the result as part of a collection.

        If `default` is not set, an exception will occur when no value was configured, otherwise, the default is used.

        description is used as the name in the configuration modal if set.
        """
        self.name: str
        self.t = t
        self.default = default
        self.description = description

    def convert(self, value):
        """
        Given a string value, convert it into the value for the config.
        """
        return self.t(value)

    async def get(self, obj: "ConfigCog"):
        """
        Get this config option, given the ConfigCog instance
        """
        if self.default is _NO_VALUE:
            try:
                return self.convert((await obj._cfg())[self.name])
            except KeyError:
                assert obj.__cog_name__ is not None
                # remove a cog if it is missing a mandatory config option
                _UNLOADED_COGS[obj.__module__] = obj
                await obj.bot.remove_cog(obj.__cog_name__)
                raise
        else:
            if (value := (await obj._cfg()).get(self.name, _NO_VALUE)) is _NO_VALUE:
                return self.default
            else:
                return self.convert(value)

    @property
    def label(self):
        """
        The label of the config option in the configuration modal.
        """
        return self.description or self.name

    def __set_name__(self, owner, name):
        if not issubclass(owner, ConfigCog):
            raise RuntimeError("Make sure you only use Cfg in ConfigCog classes")
        owner.options = getattr(owner, "options", []) + [self]
        self.name = name

    @overload
    def __get__(self, obj: None, objtype=None) -> "Cfg":
        ...

    @overload
    def __get__(self, obj: "ConfigCog", objtype=None) -> Awaitable[Any]:
        ...

    def __get__(
        self, obj: Union["ConfigCog", None], objtype=None
    ) -> "Cfg" | Awaitable[Any]:
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
        """
        Setup the ConfigCog - Make sure you user `super().__init__(bot)` if overriding this.
        """
        self.bot = bot
        self.config = bot.db.config

    async def _cfg(self) -> dict[Any, Any]:
        try:
            return await _cached_get(self.config, self.key)
        except pymongo.errors.OperationFailure as e:
            assert self.__cog_name__ is not None
            _UNLOADED_COGS[self.__module__] = self
            await self.bot.remove_cog(self.__cog_name__)
            # keep the traceback managable
            raise e from None

    def __init_subclass__(cls) -> None:
        cls.key = cls.__module__


async def gen_modal(t: str, items: list[Cfg], inst: ConfigCog) -> ui.Modal:
    """
    Given a ConfigCog instance, the title of the modal, and the list of configuration items it provides, construct a modal that provides a form for each of the fields, using the new values to update the configuration
    """
    fields: dict[str, ui.TextInput] = {}
    for item in items:
        try:
            value = str(await item.get(inst))
        except KeyError:
            value = None
        # TODO better picking of fields here
        fields[item.name] = ui.TextInput(
            label=item.label,
            default=value,
            required=False,
        )

    async def on_submit(self, interaction: Interaction):
        errors = []
        new_data: Any = {"key": inst.__module__}
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
        elif len(new_data) > 1:  # more than just key: module
            changes = [f"`{k}={v!r}`" for k, v in new_data.items()]
            send = interaction.response.send_message(
                "Updating with new values:\n" + "\n".join(changes),
                allowed_mentions=AllowedMentions.none(),
            )
            db = _cached_update(inst.config, inst.__module__, new_data)
            await asyncio.gather(send, db)
        else:
            await interaction.response.send_message(
                "No changes were made", ephemeral=True
            )

    methods = dict(on_submit=on_submit)
    return type("CogModal", (ui.Modal,), fields | methods, title="Configure " + t)()  # type: ignore
