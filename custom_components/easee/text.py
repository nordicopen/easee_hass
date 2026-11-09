"""Easee text platform (local OCPP only)."""

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import DOMAIN
from .ocpp.text import async_setup_ocpp_texts


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up text platform."""
    controller = hass.data[DOMAIN]["controller"]
    async_setup_ocpp_texts(hass, entry, async_add_entities)
    await controller.async_setup_done("text")
