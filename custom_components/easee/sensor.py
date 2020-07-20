"""
Support for Easee charger
Author: Niklas Fondberg<niklas.fondberg@gmail.com>
"""
import asyncio
from typing import List, Dict
from datetime import datetime, timedelta
import logging
from easee import Charger
from voluptuous.error import Error

from homeassistant.const import CONF_MONITORED_CONDITIONS
from homeassistant.helpers.entity import Entity
from homeassistant.helpers.event import async_track_time_interval

from .const import DOMAIN, MEASURED_CONSUMPTION_DAYS

_LOGGER = logging.getLogger(__name__)

SCAN_INTERVAL = timedelta(seconds=60)


def round_2_dec(value):
    return round(value, 2)



SENSOR_TYPES = {
    "smartCharging": {
        "key": "state.smartCharging",
        "attrs": [],
        "units": None,
        "convert_units_func": None,
        "icon": "mdi:auto-fix",
    },
    "cableLocked": {
        "key": "state.cableLocked",
        "attrs": ["state.lockCablePermanently",],
        "units": None,
        "convert_units_func": None,
        "icon": "mdi:lock",
    },
    "status": {
        "key": "state.chargerOpMode",
        "attrs": [
            "config.phaseMode",
            "state.outputPhase",
            "state.ledMode",
            "state.cableRating",
            "config.limitToSinglePhaseCharging",
            "config.localNodeType",
            "config.localAuthorizationRequired",
            "config.ledStripBrightness",
        ],
        "units": None,
        "convert_units_func": None,
        "icon": "mdi:ev-station",
    },
    "total_power": {
        "key": "state.totalPower",
        "attrs": [],
        "units": "kW",
        "convert_units_func": round_2_dec,
        "icon": "mdi:flash",
    },
    "session_energy": {
        "key": "state.sessionEnergy",
        "attrs": [],
        "units": "kWh",
        "convert_units_func": round_2_dec,
        "icon": "mdi:flash",
    },
    "energy_per_hour": {
        "key": "state.energyPerHour",
        "attrs": [],
        "units": "kWh",
        "convert_units_func": round_2_dec,
        "icon": "mdi:flash",
    },
    "online": {
        "key": "state.isOnline",
        "attrs": [
            "state.latestPulse",
            "config.wiFiSSID",
            "state.wiFiAPEnabled",
            "state.wiFiRSSI",
            "state.cellRSSI",
            "state.localRSSI",
        ],
        "units": "",
        "convert_units_func": None,
        "icon": "mdi:wifi",
    },
    "dynamicChargerCurrent": {
        "key": "state.dynamicCircuitCurrentP1",
        "attrs": [
            "state.dynamicChargerCurrent",
            "state.dynamicCircuitCurrentP1",
            "state.dynamicCircuitCurrentP2",
            "state.dynamicCircuitCurrentP3",
            "state.circuitTotalAllocatedPhaseConductorCurrentL1",
            "state.circuitTotalAllocatedPhaseConductorCurrentL2",
            "state.circuitTotalAllocatedPhaseConductorCurrentL3",
            "state.circuitTotalPhaseConductorCurrentL1",
            "state.circuitTotalPhaseConductorCurrentL2",
            "state.circuitTotalPhaseConductorCurrentL3",
            "state.circuitTotalPhaseConductorCurrentL3",
        ],
        "units": "A",
        "convert_units_func": round_2_dec,
        "icon": "mdi:sine-wave",
        "state_func": lambda state: float(
            max(
                state["dynamicCircuitCurrentP1"],
                state["dynamicCircuitCurrentP2"],
                state["dynamicCircuitCurrentP3"],
            )
        ),
    },
    "maxChargerCurrent": {
        "key": "config.circuitMaxCurrentP1",
        "attrs": [
            "config.maxChargerCurrent",  # charger rated current (static)
            "config.circuitMaxCurrentP1",  # dynamically set in app
            "config.circuitMaxCurrentP2",  # dynamically set in app
            "config.circuitMaxCurrentP3",  # dynamically set in app
        ],
        "units": "A",
        "convert_units_func": round_2_dec,
        "icon": "mdi:sine-wave",
        "state_func": lambda config: float(
            max(
                config["circuitMaxCurrentP1"],
                config["circuitMaxCurrentP2"],
                config["circuitMaxCurrentP3"],
            )
        ),
    },
    "current": {
        "key": "state.inCurrentT2",
        "attrs": [
            "state.outputCurrent",  # outputCurrent doesn't seem to show actual current, but allowed?
            "state.inCurrentT2",
            "state.inCurrentT3",
            "state.inCurrentT4",
            "state.inCurrentT5",
        ],
        "units": "A",
        "convert_units_func": round_2_dec,
        "icon": "mdi:sine-wave",
        "state_func": lambda state: float(
            max(
                state["inCurrentT2"],
                state["inCurrentT3"],
                state["inCurrentT4"],
                state["inCurrentT5"],
            )
        ),
    },
    "voltage": {
        "key": "state.voltage",
        "attrs": [
            "state.inVoltageT1T2",
            "state.inVoltageT1T3",
            "state.inVoltageT1T4",
            "state.inVoltageT1T5",
            "state.inVoltageT2T3",
            "state.inVoltageT2T4",
            "state.inVoltageT2T5",
            "state.inVoltageT3T4",
            "state.inVoltageT3T5",
            "state.inVoltageT4T5",
        ],
        "units": "V",
        "convert_units_func": round_2_dec,
        "icon": "mdi:sine-wave",
    },
    "reasonForNoCurrent": {
        "key": "state.reasonForNoCurrent",
        "attrs": ["state.reasonForNoCurrent", "state.reasonForNoCurrent_desc",],
        "units": "",
        "convert_units_func": None,
        "icon": "mdi:alert-circle",
    },
    "isEnabled": {
        "key": "config.isEnabled",
        "attrs": [],
        "units": "",
        "convert_units_func": None,
        "icon": "mdi:power-standby",
    },
    "enableIdleCurrent": {
        "key": "config.enableIdleCurrent",
        "attrs": [],
        "units": "",
        "convert_units_func": None,
        "icon": "mdi:current-dc",
    },
    "update_available": {
        "key": "state.chargerFirmware",
        "attrs": ["state.chargerFirmware", "state.latestFirmware",],
        "units": "",
        "convert_units_func": None,
        "icon": "mdi:file-download",
        "state_func": lambda state: int(state["chargerFirmware"]) < int(state["latestFirmware"]),
    },
}


async def async_setup_entry(hass, entry, async_add_entities):
    """Set up the Easee sensor."""
    chargers: List[Charger] = hass.data[DOMAIN]["chargers"]
    config = hass.data[DOMAIN]["config"]
    monitored_conditions = config.options.get(CONF_MONITORED_CONDITIONS, ["status"])
    sensors = []
    for charger in chargers:
        _LOGGER.debug("Found charger: %s %s", charger.id, charger.name)
        for key in monitored_conditions:
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
                    state_func=data.get("state_func", None),
                )
            )

        monitored_days = config.options.get(MEASURED_CONSUMPTION_DAYS, [])
        for interval in monitored_days:
            _LOGGER.info("Will measure days: %s", interval)
            sensors.append(
                ChargerConsumptionSensor(charger, f"consumption_days_{interval}", int(interval))
            )

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
        tasks = [charger.async_update() for charger in self._chargers]
        if tasks:
            await asyncio.wait(tasks)

        # Schedule an update for all included sensors
        for sensor in self._sensors:
            sensor.async_schedule_update_ha_state(True)


class ChargerSensor(Entity):
    """Implementation of Easee charger sensor """

    def __init__(
        self, charger, name, state_key, units, convert_units_func, attrs_keys, icon, state_func=None
    ):
        """Initialize the sensor."""
        self.charger = charger
        self._sensor_name = name
        self._state_key = state_key
        self._units = units
        self._convert_units_func = convert_units_func
        self._attrs_keys = attrs_keys
        self._icon = icon
        self._state_func = state_func
        self._state = None

    @property
    def name(self):
        """Return the name of the sensor."""
        return f"{DOMAIN}_charger_{self.charger.id}_{self._sensor_name}"

    @property
    def unique_id(self) -> str:
        """Return a unique ID."""
        return f"{self.charger.id}_{self._sensor_name}"

    @property
    def device_info(self) -> Dict[str, any]:
        """Return the device information."""
        return {
            "identifiers": {(DOMAIN, self.charger.id)},
            "name": self.charger.name,
            "manufacturer": "Easee",
            "model": "Charging Robot",
        }

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
            if self._state_func is not None:
                charger_state = await self.charger.get_state(from_cache=True)
                charger_config = await self.charger.get_config(from_cache=True)
                try:
                    self._state = self._state_func(charger_state)
                except:
                    self._state = self._state_func(charger_config)
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
    def unique_id(self) -> str:
        """Return a unique ID."""
        return f"{self.charger.id}_{self._sensor_name}"

    @property
    def device_info(self) -> Dict[str, any]:
        """Return the device information."""
        return {
            "identifiers": {(DOMAIN, self.charger.id)},
            "name": self.charger.name,
            "manufacturer": "Easee",
            "model": "Charging Robot",
        }

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
            "ChargerConsumptionSensor async_update : %s %s", self.charger.name, self._sensor_name,
        )
        now = datetime.now()
        self._state = await self.charger.get_consumption_between_dates(
            now - timedelta(0, 86400 * self._days), now
        )
