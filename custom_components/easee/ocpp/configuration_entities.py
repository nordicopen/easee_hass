"""Entities for the charger's OCPP configuration keys (GetConfiguration).

Which keys exist is only known once the charger is connected, so the platforms add
these entities when the keys show up and remember which ones they already added.
"""

from __future__ import annotations

from collections.abc import Callable

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity import Entity, EntityDescription
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .charge_point import CommandFailedError
from .entity import OcppEntity
from .hub import OcppHub, signal_state_updated
from .models import ConfigurationValue, Serial
from .server import HUB_DATA_KEY

type ConfigurationKey = str
type BelongsToPlatform = Callable[[ConfigurationValue], bool]
type ConfigurationEntityFactory = Callable[[OcppHub, Serial, ConfigurationKey], Entity]


def is_switch_key(value: ConfigurationValue) -> bool:
    """Writable booleans become switches."""
    return not value.readonly and value.is_boolean()


def is_number_key(value: ConfigurationValue) -> bool:
    """Writable integers become numbers."""
    return not value.readonly and value.is_integer()


def is_text_key(value: ConfigurationValue) -> bool:
    """Every other writable key becomes a text entity."""
    return not value.readonly and not value.is_boolean() and not value.is_integer()


def is_read_only_key(value: ConfigurationValue) -> bool:
    """Read-only keys become diagnostic sensors."""
    return value.readonly


class ConfigurationKeyEntity(OcppEntity):
    """One configuration key of the charger.

    Platform classes read their own description type (e.g. TextEntityDescription.mode),
    so every subclass names the description class of its platform.
    """

    description_class: type[EntityDescription] = EntityDescription

    def __init__(self, hub: OcppHub, serial: Serial, key: ConfigurationKey) -> None:
        """Name the entity after the OCPP key; there is no sensible translation for vendor keys."""
        is_read_only = hub.state(serial).configuration[key].readonly
        description = self.description_class(
            key=f"config_{key}",
            entity_category=EntityCategory.DIAGNOSTIC
            if is_read_only
            else EntityCategory.CONFIG,
            entity_registry_enabled_default=not is_read_only,
        )
        super().__init__(hub, serial, description)
        self._configuration_key = key
        self._attr_translation_key = None
        self._attr_name = f"OCPP {key}"

    @property
    def configuration_value(self) -> str | None:
        """Current value as reported by the charger."""
        return self.charge_point_state.configuration_value(self._configuration_key)

    async def _write(self, value: str) -> None:
        try:
            status = await self._hub.charge_point(self._serial).change_configuration(
                self._configuration_key, value
            )
        except CommandFailedError as error:
            raise HomeAssistantError(str(error)) from error
        if status == "RebootRequired":
            raise HomeAssistantError(
                f"{self._configuration_key} takes effect after a reboot of the charger"
            )


@callback
def async_add_configuration_entities(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
    belongs_to_platform: BelongsToPlatform,
    create_entity: ConfigurationEntityFactory,
) -> None:
    """Add entities for this platform's keys now and whenever new keys are read."""
    hub: OcppHub | None = hass.data.get(HUB_DATA_KEY)
    if hub is None:
        return
    for serial in hub.serials():
        added_keys: set[ConfigurationKey] = set()

        @callback
        def add_new_keys(
            serial: Serial = serial, added_keys: set[ConfigurationKey] = added_keys
        ) -> None:
            configuration = hub.state(serial).configuration
            new_keys = [
                key
                for key, value in configuration.items()
                if key not in added_keys and belongs_to_platform(value)
            ]
            added_keys.update(new_keys)
            if new_keys:
                async_add_entities(
                    [create_entity(hub, serial, key) for key in new_keys]
                )

        add_new_keys()
        entry.async_on_unload(
            async_dispatcher_connect(hass, signal_state_updated(serial), add_new_keys)
        )
