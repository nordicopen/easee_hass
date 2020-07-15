"""
Support for Easee charger
Author: Niklas Fondberg<niklas.fondberg@gmail.com>
"""
import asyncio
from datetime import datetime, timedelta
import logging

import voluptuous as vol

from homeassistant.components.sensor import PLATFORM_SCHEMA
from homeassistant.const import CONF_MONITORED_CONDITIONS
from homeassistant.exceptions import PlatformNotReady
from homeassistant.helpers.aiohttp_client import async_get_clientsession
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.entity import Entity
from homeassistant.util.json import load_json, save_json
from homeassistant.util import Throttle
from homeassistant.helpers.event import async_track_time_interval
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME

from easee import Easee, Charger
from .services import async_setup_services

DOMAIN = "easee"
_LOGGER = logging.getLogger(__name__)

MEASURED_CONSUMPTION_DAYS = "measured_consumption_days"
SCAN_INTERVAL = timedelta(seconds=60)


def round_2_dec(value):
    return round(value, 2)


def watts_to_kilowatts(value):
    return round_2_dec(value * 1000)


SENSOR_TYPES = {
    "status": {
        "key": "state.chargerOpMode",
        "attrs": ["state.voltage", "config.phaseMode"],
        "units": None,
        "convert_units_func": None,
        "icon": "mdi:flash",
    },
    "total_power": {
        "key": "state.totalPower",
        "attrs": ["state.latestPulse", "state.inCurrentT2", "state.inCurrentT3", "state.inCurrentT4", "state.inCurrentT5", "state.inVoltageT1T2", "state.inVoltageT1T3", "state.inVoltageT1T4", "state.inVoltageT1T5", "state.inVoltageT2T3", "state.inVoltageT2T4", "state.inVoltageT2T5", "state.inVoltageT3T4", "state.inVoltageT3T5", "state.inVoltageT4T5"],
        "units": "W",
        "convert_units_func": watts_to_kilowatts,
        "icon": "mdi:flash",
    },
    "session_energy": {
        "key": "state.sessionEnergy",
        "attrs": [],
        "units": "Wh",
        "convert_units_func": round_2_dec,
        "icon": "mdi:flash",
    },
    "energy_per_hour": {
        "key": "state.energyPerHour",
        "attrs": [],
        "units": "Wh",
        "convert_units_func": round_2_dec,
        "icon": "mdi:flash",
    },
    "online": {
        "key": "state.isOnline",
        "attrs": [],
        "units": "",
        "convert_units_func": None,
        "icon": "mdi:flash",
    },
    "cable_locked": {
        "key": "state.cableLocked",
        "attrs": [],
        "units": "",
        "convert_units_func": None,
        "icon": "mdi:flash",
    },
    "phase_mode": {
        "key": "config.phaseMode",
        "attrs": ["config.localNodeType"],
        "units": "",
        "convert_units_func": None,
        "icon": "mdi:flash",
    },
    "current_firmware": {
        "key": "state.chargerFirmware",
        "attrs": [],
        "units": "",
        "convert_units_func": None,
        "icon": "mdi:flash",
    },
    "latest_firmware": {
        "key": "state.latestFirmware",
        "attrs": [],
        "units": "",
        "convert_units_func": None,
        "icon": "mdi:flash",
    },
}

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {
        vol.Required(CONF_USERNAME): cv.string,
        vol.Required(CONF_PASSWORD): cv.string,
        vol.Optional(CONF_MONITORED_CONDITIONS, default=["status"]): vol.All(
            cv.ensure_list, [vol.In(SENSOR_TYPES)]
        ),
        vol.Optional(MEASURED_CONSUMPTION_DAYS, default=[]): vol.All(cv.ensure_list),
    }
)


async def async_setup_platform(hass, config, async_add_entities, discovery_info=None):
    """Set up the Easee sensor."""

    session = async_get_clientsession(hass)
    username = config.get(CONF_USERNAME)
    password = config.get(CONF_PASSWORD)

    if DOMAIN not in hass.data:
        hass.data[DOMAIN] = {}

    if "easee" not in hass.data[DOMAIN]:
        easee = Easee(username, password)
        hass.data[DOMAIN] = {"easee": easee}
    else:
        easee = hass.data[DOMAIN]["easee"]

    sensors = []
    chargers = await easee.get_chargers()
    _LOGGER.info("KEYS\n%s", list(SENSOR_TYPES))
    _LOGGER.debug("Found chargers: %d", len(chargers))

    hass.data[DOMAIN]["chargers"] = chargers

    for charger in chargers:
        _LOGGER.debug("Found charger: %s %s", charger.id, charger.name)
        for key in config[CONF_MONITORED_CONDITIONS]:
            data = SENSOR_TYPES[key]
            _LOGGER.debug("Adding sensor: %s for charger %s", key, charger.name)
            sensors.append(
                ChargerSensor(
                    charger=charger,
                    name=key,
                    state_key=data["key"],
                    units=data["units"],
                    convert_units_func=data["convert_units_func"],
                    attrs_keys=data["attrs"],
                    icon=data["icon"],
                )
            )
        for interval in config[MEASURED_CONSUMPTION_DAYS]:
            _LOGGER.info("Will measure days: %d", interval)
            sensors.append(
                ChargerConsumptionSensor(charger, f"consumption_days_{interval}", interval)
            )

    charger_data = ChargersData(chargers, sensors)

    hass.async_add_job(charger_data.async_refresh)
    async_track_time_interval(hass, charger_data.async_refresh, SCAN_INTERVAL)
    async_add_entities(sensors)

    # Setup services
    await async_setup_services(hass)


class ChargersData:
    """Representation of a Sensor."""

    def __init__(self, chargers, sensors):
        """Initialize the sensor."""
        self._chargers = chargers
        self._sensors = sensors

    async def async_refresh(self, now=None):
        """Fetch new state data for the sensor. """
        tasks = [charger.async_update() for charger in self._chargers]
        if tasks:
            await asyncio.wait(tasks)

        # Schedule an update for all included sensors
        for sensor in self._sensors:
            sensor.async_schedule_update_ha_state(True)


class ChargerSensor(Entity):
    """Implementation of Easee charger sensor """

    def __init__(self, charger, name, state_key, units, convert_units_func, attrs_keys, icon):
        """Initialize the sensor."""
        self.charger = charger
        self._sensor_name = name
        self._state_key = state_key
        self._units = units
        self._convert_units_func = convert_units_func
        self._attrs_keys = attrs_keys
        self._icon = icon
        self._state = None

    @property
    def name(self):
        """Return the name of the sensor."""
        return f"{DOMAIN}_charger_{self.charger.id}_{self._sensor_name}"

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
            attrs = {"name": self.charger.name, "id": self.charger.id}
            for attr_key in self._attrs_keys:
                attrs[attr_key.split(".")[1]] = self.get_value_from_key(attr_key)
            return attrs
        except IndexError:
            return {}

    @property
    def icon(self):
        """Icon to use in the frontend, if any."""
        return self._icon

    @property
    def should_poll(self):
        """No polling needed."""
        return False

    def get_value_from_key(self, key):
        first, second = key.split(".")
        if first == "config":
            return self.charger.get_cached_config_entry(second)
        elif first == "state":
            return self.charger.get_cached_state_entry(second)
        else:
            _LOGGER.error("Unknown first part of key: %s", key)
            raise IndexError("Unknown first part of key")

    async def async_update(self):
        """Get the latest data and update the state."""
        _LOGGER.debug("ChargerSensor async_update : %s %s", self.charger.name, self._sensor_name)
        try:
            self._state = self.get_value_from_key(self._state_key)
            if self._convert_units_func is not None:
                self._state = self._convert_units_func(self._state)
        except IndexError:
            raise IndexError("Wrong key for sensor: %s", self._key)


class ChargerConsumptionSensor(Entity):
    """Implementation of Easee charger sensor """

    def __init__(self, charger, name, days):
        """Initialize the sensor."""
        self.charger = charger
        self._sensor_name = name
        self._days = days
        self._state = None

    @property
    def name(self):
        """Return the name of the sensor."""
        return f"{DOMAIN}_charger_{self.charger.id}_{self._sensor_name}"

    @property
    def unit_of_measurement(self):
        """Return the unit of measurement of this entity, if any."""
        return "kW"

    @property
    def available(self):
        """Return True if entity is available."""
        return self._state is not None

    @property
    def state(self):
        """Return online status"""
        return round_2_dec(self._state)

    @property
    def state_attributes(self):
        """Return the state attributes."""
        return {"name": self.charger.name, "id": self.charger.id}

    @property
    def icon(self):
        """Icon to use in the frontend, if any."""
        return "mdi:flash"

    async def async_update(self):
        """Get the latest data and update the state."""
        _LOGGER.debug(
            "ChargerConsumptionSensor async_update : %s %s", self.charger.name, self._sensor_name
        )
        now = datetime.now()
        self._state = await self.charger.get_consumption_between_dates(
            now - timedelta(0, 86400 * self._days), now
        )

