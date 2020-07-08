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
from homeassistant.helpers.event import async_track_time_interval
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME

from .easee import Easee, Charger

DOMAIN = "easee"

_LOGGER = logging.getLogger(__name__)

SCAN_INTERVAL = timedelta(seconds=60)

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {vol.Required(CONF_USERNAME): cv.string, vol.Required(CONF_PASSWORD): cv.string}
)


async def async_setup_platform(hass, config, async_add_entities, discovery_info=None):
    """Set up the Easee sensor."""

    session = async_get_clientsession(hass)
    username = config.get(CONF_USERNAME)
    password = config.get(CONF_PASSWORD)
    easee = Easee(username, password)

    sensors = []
    chargers = await easee.get_chargers()

    _LOGGER.info("Got chargers: %d", len(chargers))

    for charger in chargers:
        await charger.async_update()
        _LOGGER.info("Found charger: %s %s", charger.id, charger.name)
        sensors.append(ChargerSensor(charger))

    charger_data = ChargersData(chargers, sensors)

    hass.async_add_job(charger_data.async_refresh)
    async_track_time_interval(hass, charger_data.async_refresh, SCAN_INTERVAL)
    async_add_entities(sensors)


class ChargersData:
    """Representation of a Sensor."""

    def __init__(self, chargers, sensors):
        """Initialize the sensor."""
        self._chargers = chargers
        self._sensors = sensors

    async def async_refresh(self, now=None):
        """Fetch new state data for the sensor. """
        _LOGGER.info("ChargersData async_refresh")
        tasks = [charger.async_update() for charger in self._chargers]
        if tasks:
            await asyncio.wait(tasks)
        # Schedule an update for all included sensors
        for sensor in self._sensors:
            sensor.async_schedule_update_ha_state(True)
        _LOGGER.info("ChargersData async_refresh DONE")


class ChargerSensor(Entity):
    """Implementation of Easee charger sensor """

    def __init__(
        self,
        charger,
        state_key="state.chargerOpMode",
        units=None,
        attrs_keys=["state.voltage", "config.phaseMode"],
    ):
        """Initialize the sensor."""
        self.charger = charger
        self.id = charger.id
        self._name = charger.name
        self._state_key = state_key
        self._units = units
        self._attrs_keys = attrs_keys
        self._state = None

    @property
    def name(self):
        """Return the name of the sensor."""
        return f"{DOMAIN}_charger_{self.id}"

    @property
    def unique_id(self):
        """Return the unique id."""
        return f"{self.id} {self._name}"

    @property
    def unit_of_measurement(self):
        """Return the unit of measurement of this entity, if any."""
        return self._units

    @property
    def available(self):
        """Return True if entity is available."""
        return self._state is not None

    @property
    def state(self):
        """Return online status"""
        return self._state

    @property
    def state_attributes(self):
        """Return the state attributes."""
        try:
            attrs = {}
            for attr_key in self._attrs_keys:
                first, second = attr_key.split(".")
                attrs[second] = self.get_value_from_key(attr_key)
            return attrs
        except IndexError:
            return {}

    @property
    def icon(self):
        """Icon to use in the frontend, if any."""
        return "mdi:flash"

    @property
    def should_poll(self):
        """No polling needed."""
        return False

    def get_value_from_key(self, key):
        first, second = key.split(".")
        if first == "config":
            return self.charger.config[second]
        elif first == "state":
            return self.charger.state[second]
        else:
            _LOGGER.error("Unknown first part of key: %s", key)
            raise IndexError("Unknown first part of key")

    async def async_update(self):
        """Get the latest data and update the state."""
        _LOGGER.debug("async_update charger: %s", self._name)
        try:
            self._state = self.get_value_from_key(self._state_key)
        except IndexError:
            raise IndexError("Wrong key for sensor: %s", self._key)
