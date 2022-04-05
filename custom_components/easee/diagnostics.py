"""Diagnostics support for Easee."""
from __future__ import annotations

from typing import Any

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceEntry

from .const import DOMAIN

TO_REDACT = {
    CONF_PASSWORD,
    CONF_USERNAME,
}
TO_REDACT_DATA = {}
TO_REDACT_SITES = {
    "id",
    "siteKey",
    "address",
    "contactInfo",
    "siteId",
    "masterBackPlateId",
}


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, config_entry: ConfigEntry
) -> dict:
    """Return diagnostics for a config entry."""

    diagnostics_data = {
        "account": async_redact_data(config_entry.data, TO_REDACT),
        "options": async_redact_data(config_entry.options, TO_REDACT),
        "sites": async_redact_data(hass.data[DOMAIN]["diagnostics"], TO_REDACT_SITES),
    }

    return diagnostics_data


async def async_get_device_diagnostics(
    hass: HomeAssistant, config_entry: ConfigEntry, device: DeviceEntry
) -> dict[str, Any]:
    """Return diagnostics for a device."""
    info = {}
    info["manufacturer"] = device.manufacturer
    info["model"] = device.model

    diagnostics_data = {
        "account": async_redact_data(config_entry.data, TO_REDACT),
        "data": async_redact_data(info, TO_REDACT_DATA),
    }

    return diagnostics_data
