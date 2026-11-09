"""Text entities for writable configuration keys that are neither boolean nor numeric."""

from __future__ import annotations

from homeassistant.components.text import TextEntity, TextEntityDescription
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .configuration_entities import (
    ConfigurationKeyEntity,
    async_add_configuration_entities,
    is_text_key,
)

# OCPP allows 500 characters, but an HA state is limited to 255 (MAX_LENGTH_STATE_STATE).
MAX_VALUE_LENGTH = 255


class OcppConfigurationText(ConfigurationKeyEntity, TextEntity):
    """A textual OCPP configuration key, e.g. MeterValuesSampledData."""

    description_class = TextEntityDescription
    _attr_native_max = MAX_VALUE_LENGTH

    @property
    def native_value(self) -> str | None:
        """Current value."""
        return self.configuration_value

    async def async_set_value(self, value: str) -> None:
        """Write the key."""
        await self._write(value)


def async_setup_ocpp_texts(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """One text entity per textual configuration key."""
    async_add_configuration_entities(
        hass, entry, async_add_entities, is_text_key, OcppConfigurationText
    )
