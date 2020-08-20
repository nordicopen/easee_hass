""" Easee charger component """
import asyncio
import logging
from typing import List
from easee import Easee, Charger, Site

import voluptuous as vol
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_USERNAME, CONF_PASSWORD, CONF_MONITORED_CONDITIONS
from homeassistant.core import HomeAssistant
from homeassistant.helpers import (
    aiohttp_client,
    config_validation as cv,
)

from .const import DOMAIN, MEASURED_CONSUMPTION_DAYS, VERSION, CONF_MONITORED_SITES
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
    _LOGGER.debug("Setting up Easee component version %s", VERSION)
    username = entry.data.get(CONF_USERNAME)
    password = entry.data.get(CONF_PASSWORD)
    
    client_session = aiohttp_client.async_get_clientsession(hass)
    easee = Easee(username, password, client_session)
    sites: List[Site] = await easee.get_sites()

    hass.data[DOMAIN]["session"] = easee
    hass.data[DOMAIN]["config"] = entry
    hass.data[DOMAIN]["sites"] = sites
    hass.data[DOMAIN]["circuits"] = []
    hass.data[DOMAIN]["chargers"] = []
    for site in sites:
        for circuit in site.get_circuits():
            hass.data[DOMAIN]["circuits"].append(circuit)
            for charger in circuit.get_chargers():
                hass.data[DOMAIN]["chargers"].append(charger)

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
        hass.data[DOMAIN] = {}

    return unload_ok
