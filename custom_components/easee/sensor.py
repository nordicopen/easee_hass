"""
Support for Easee charger
Author: Niklas Fondberg<niklas.fondberg@gmail.com>
"""
import asyncio
from datetime import timedelta
import logging

import voluptuous as vol

from homeassistant.components.sensor import PLATFORM_SCHEMA
from homeassistant.const import ATTR_ATTRIBUTION, CONF_NAME, TIME_MINUTES
from homeassistant.exceptions import PlatformNotReady
from homeassistant.helpers.aiohttp_client import async_get_clientsession
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.entity import Entity
from homeassistant.util.json import load_json, save_json
from homeassistant.util import Throttle
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME

from .easee import EaseeSession, Charger, ChargerConfig, ChargerState

DOMAIN = "easee"

_LOGGER = logging.getLogger(__name__)

SCAN_INTERVAL = timedelta(seconds=60)


PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {vol.Required(CONF_USERNAME): cv.string, vol.Required(CONF_PASSWORD): cv.string}
)


"""
CONFIG_FILE = ".easee-token"
conf = load_json(hass.config.path(CONFIG_FILE))
save_json(hass.config.path(CONFIG_FILE), conf)
"""


async def async_setup_platform(hass, config, async_add_entities, discovery_info=None):
    """Set up the Easee sensor."""

    session = async_get_clientsession(hass)
    username = config.get(CONF_USERNAME)
    password = config.get(CONF_PASSWORD)
    easee = EaseeSession(username, password)
    await easee.connect()

    sensors = []
    chargers = await easee.get_chargers()
    for charger in chargers:
        await charger.async_update()
        _LOGGER.info("Found charger: %s %s", charger.id, charger.name)
        sensors.append(ChargersSensor(easee, charger))

    tasks = [sensor.async_update() for sensor in sensors]
    if tasks:
        await asyncio.wait(tasks)
    # if not all(sensor.data.something for sensor in sensors):
    #     raise PlatformNotReady

    async_add_entities(sensors)


class ChargersSensor(Entity):
    """Implementation of an RMV departure sensor."""

    def __init__(self, easeesession, charger: Charger):
        """Initialize the sensor."""
        self.easeesession = easeesession
        self.charger = charger
        self.id = charger.id
        self._name = charger.name
        self._state = None

    @property
    def name(self):
        """Return the name of the sensor."""
        return f"{DOMAIN}_charger_{self.id}"

    @property
    def available(self):
        """Return True if entity is available."""
        return self._state is not None

    @property
    def state(self):
        """Return online status"""
        return "online" if self._state else "offline"

    @property
    def state_attributes(self):
        """Return the state attributes."""
        try:
            return {
                "id": self.id,
                "name": self._name,
                "status": self.charger.state.status,
                "total_energy": self.charger.state.total_power,
                "session_energy": self.charger.state.session_energy,
                "smart_charging": self.charger.state.smart_charging,
                "cable_locked": self.charger.state.cable_locked,
            }
        except IndexError:
            return {}

    @property
    def icon(self):
        """Icon to use in the frontend, if any."""
        return "mdi:flash"

    async def async_update(self):
        """Get the latest data and update the state."""
        _LOGGER.info("updating charger: %s", self.name)
        await self.charger.async_update()
        self._state = self.charger.state.online
