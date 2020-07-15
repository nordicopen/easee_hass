""" Easee charger component """
import asyncio
import logging
from typing import List
from easee import Easee, Charger

import voluptuous as vol
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_USERNAME, CONF_PASSWORD, CONF_MONITORED_CONDITIONS
from homeassistant.core import HomeAssistant
from homeassistant.helpers import (
    #    aiohttp_client,
    config_validation as cv,
)

from .const import DOMAIN, MEASURED_CONSUMPTION_DAYS
from .services import async_setup_services
from .sensor import SENSOR_TYPES
from .config_flow import EaseeConfigFlow  # noqa

_LOGGER = logging.getLogger(__name__)

PLATFORMS = ("sensor",)

CONFIG_SCHEMA = vol.Schema(
    {
        DOMAIN: vol.Schema(
            {
                vol.Optional(CONF_USERNAME): cv.string,
                vol.Optional(CONF_PASSWORD): cv.string,
                vol.Optional(CONF_MONITORED_CONDITIONS, default=["status"]): vol.All(
                    cv.ensure_list, [vol.In(SENSOR_TYPES)]
                ),
                vol.Optional(MEASURED_CONSUMPTION_DAYS, default=[]): vol.All(
                    cv.ensure_list
                ),
            }
        )
    },
    extra=vol.ALLOW_EXTRA,
)


async def async_setup(hass: HomeAssistant, config: dict):
    """Set up the Easee integration component."""
    if DOMAIN not in hass.data:
        hass.data[DOMAIN] = {}
    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry):
    """Set up Easee integration from a config entry."""
    if DOMAIN not in hass.data:
        hass.data[DOMAIN] = {}
    _LOGGER.info("BLABLABLA\n\nasync_setup_entry in __init__ %s", DOMAIN)
    # session = aiohttp_client.async_get_clientsession(hass) <- TODO test me
    username = entry.data.get(CONF_USERNAME)
    password = entry.data.get(CONF_PASSWORD)
    easee = Easee(username, password)
    chargers: List[Charger] = await easee.get_chargers()

    hass.data[DOMAIN]["session"] = easee
    hass.data[DOMAIN]["config"] = entry
    hass.data[DOMAIN]["chargers"] = chargers

    # Setup services
    await async_setup_services(hass)

    for component in PLATFORMS:
        hass.async_create_task(
            hass.config_entries.async_forward_entry_setup(entry, component)
        )

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry):
    """Unload a config entry."""
    unload_ok = all(
        await asyncio.gather(
            *[
                hass.config_entries.async_forward_entry_unload(entry, component)
                for component in PLATFORMS
            ]
        )
    )
    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id)

    return unload_ok
