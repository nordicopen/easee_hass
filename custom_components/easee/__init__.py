"""Easee charger component."""
import asyncio
import logging

import voluptuous as vol
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_USERNAME, CONF_PASSWORD, CONF_MONITORED_CONDITIONS
from homeassistant.core import HomeAssistant
from homeassistant.helpers import (
    config_validation as cv,
    device_registry,
)

from .const import (
    DOMAIN,
    EASEE_ENTITIES,
    LISTENER_FN_CLOSE,
    MEASURED_CONSUMPTION_DAYS,
    VERSION,
    PLATFORMS,
)
from .services import async_setup_services
from .controller import Controller

_LOGGER = logging.getLogger(__name__)

CONFIG_SCHEMA = vol.Schema(
    {
        DOMAIN: vol.Schema(
            {
                vol.Optional(CONF_USERNAME): cv.string,
                vol.Optional(CONF_PASSWORD): cv.string,
                vol.Optional(CONF_MONITORED_CONDITIONS, default=["status"]): vol.All(
                    cv.ensure_list, [vol.In(EASEE_ENTITIES)]
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
    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry):
    """Set up Easee integration from a config entry."""
    if DOMAIN not in hass.data:
        hass.data[DOMAIN] = {}
    _LOGGER.debug("Setting up Easee component version %s", VERSION)
    username = entry.data.get(CONF_USERNAME)
    password = entry.data.get(CONF_PASSWORD)

    controller = Controller(username, password, hass, entry)
    await controller.initialize()
    hass.data[DOMAIN]["controller"] = controller

    for component in PLATFORMS:
        hass.async_create_task(
            hass.config_entries.async_forward_entry_setup(entry, component)
        )

    # Setup services
    await async_setup_services(hass)

    undo_listener = entry.add_update_listener(config_entry_update_listener)

    hass.data[DOMAIN][entry.entry_id] = {
        LISTENER_FN_CLOSE: undo_listener,
    }

    await controller.add_schedulers()
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
        hass.data[DOMAIN][entry.entry_id][LISTENER_FN_CLOSE]()
        hass.data[DOMAIN] = {}

    return unload_ok


async def config_entry_update_listener(hass: HomeAssistant, entry: ConfigEntry):
    """Handle options update, delete device and set it up again as suggested on discord #devs_core."""
    await hass.config_entries.async_reload(entry.entry_id)

    dev_reg = await device_registry.async_get_registry(hass)
    devices_to_purge = []
    for device in dev_reg.devices.values():
        for identifier in device.identifiers:
            if DOMAIN in identifier:
                devices_to_purge.append(device.id)

    _LOGGER.debug("Purging device: %s", devices_to_purge)
    for device_id in devices_to_purge:
        dev_reg.async_remove_device(device_id)
