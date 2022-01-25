"""Diagnostics support for Easee."""
from __future__ import annotations

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant

from .const import DOMAIN

TO_REDACT = {CONF_PASSWORD, CONF_USERNAME,}


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, config_entry: ConfigEntry
) -> dict:
    """Return diagnostics for a config entry."""

    diagnostics_data = {
        "account": async_redact_data(config_entry.data, TO_REDACT),
        "options": async_redact_data(config_entry.options, TO_REDACT),
        # "data": coordinator.data, # Add more relevant data here
    }

    return diagnostics_data
