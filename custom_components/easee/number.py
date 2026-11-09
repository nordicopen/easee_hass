"""Easee number platform (local OCPP only)."""

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import DOMAIN
from .ocpp import async_add_ocpp_entities
from .ocpp.number import async_setup_ocpp_numbers, ocpp_numbers


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up number platform."""
    controller = hass.data[DOMAIN]["controller"]
    async_add_ocpp_entities(hass, async_add_entities, ocpp_numbers)
    async_setup_ocpp_numbers(hass, entry, async_add_entities)
    await controller.async_setup_done("number")
