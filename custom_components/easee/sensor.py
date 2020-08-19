"""
Support for Easee charger
Author: Niklas Fondberg<niklas.fondberg@gmail.com>
"""
import asyncio
from typing import List, Dict, Callable, Any
from datetime import datetime, timedelta
import logging

from easee import Charger, ChargerState, ChargerConfig, Site, Circuit
from easee.charger import ChargerSchedule

from voluptuous.error import Error

from homeassistant.const import CONF_MONITORED_CONDITIONS
from homeassistant.helpers import device_registry
from homeassistant.helpers.entity import Entity
from homeassistant.helpers.event import async_track_time_interval
from homeassistant.util import dt

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
            "site.id",
            "site.name",
            "site.siteKey",
            "circuit.id",
            "circuit.ratedCurrent",
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
    "outputCurrent": {
        "key": "state.outputCurrent",
        "attrs": [],
        "units": "A",
        "convert_units_func": round_2_dec,
        "icon": "mdi:sine-wave",
    },
    "inCurrent": {
        "key": "state.inCurrentT2",
        "attrs": [
            "state.outputCurrent",
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
    "circuitCurrent": {
        "key": "state.circuitTotalPhaseConductorCurrentL1",
        "attrs": [
            "circuit.id",
            "circuit.circuitPanelId",
            "circuit.panelName",
            "circuit.ratedCurrent",
            "state.circuitTotalAllocatedPhaseConductorCurrentL1",
            "state.circuitTotalAllocatedPhaseConductorCurrentL2",
            "state.circuitTotalAllocatedPhaseConductorCurrentL3",
            "state.circuitTotalPhaseConductorCurrentL1",
            "state.circuitTotalPhaseConductorCurrentL2",
            "state.circuitTotalPhaseConductorCurrentL3",
        ],
        "units": "A",
        "convert_units_func": round_2_dec,
        "icon": "mdi:sine-wave",
        "state_func": lambda state: float(
            max(
                state["circuitTotalPhaseConductorCurrentL1"]
                if state["circuitTotalPhaseConductorCurrentL1"] is not None
                else 0.0,
                state["circuitTotalPhaseConductorCurrentL2"]
                if state["circuitTotalPhaseConductorCurrentL2"] is not None
                else 0.0,
                state["circuitTotalPhaseConductorCurrentL3"]
                if state["circuitTotalPhaseConductorCurrentL3"] is not None
                else 0.0,
            )
        ),
    },
    "dynamicCircuitCurrent": {
        "key": "state.dynamicCircuitCurrentP1",
        "attrs": [
            "circuit.id",
            "circuit.circuitPanelId",
            "circuit.panelName",
            "circuit.ratedCurrent",
            "state.dynamicCircuitCurrentP1",
            "state.dynamicCircuitCurrentP2",
            "state.dynamicCircuitCurrentP3",
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
    "maxCircuitCurrent": {
        "key": "config.circuitMaxCurrentP1",
        "attrs": [
            "circuit.id",
            "circuit.circuitPanelId",
            "circuit.panelName",
            "circuit.ratedCurrent",
            "config.circuitMaxCurrentP1",
            "config.circuitMaxCurrentP2",
            "config.circuitMaxCurrentP3",
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
    "dynamicChargerCurrent": {
        "key": "state.dynamicChargerCurrent",
        "attrs": ["state.dynamicChargerCurrent",],
        "units": "A",
        "convert_units_func": round_2_dec,
        "icon": "mdi:sine-wave",
    },
    "maxChargerCurrent": {
        "key": "config.maxChargerCurrent",
        "attrs": ["config.maxChargerCurrent",],
        "units": "A",
        "convert_units_func": round_2_dec,
        "icon": "mdi:sine-wave",
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
        "attrs": ["state.reasonForNoCurrent", "state.reasonForNoCurrent",],
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
        "state_func": lambda state: int(state["chargerFirmware"])
        < int(state["latestFirmware"]),
    },
    "basic_schedule": {
        "key": "schedule.id",
        "attrs": [
            "schedule.id",
            "schedule.chargeStartTime",
            "schedule.chargeStopTime",
            "schedule.repeat",
        ],
        "units": "",
        "convert_units_func": None,
        "icon": "mdi:clock-check",
        "state_func": lambda schedule: True if schedule is not None else False,
    },
    "costPerKWh": {
        "key": "site.costPerKWh",
        "attrs": [
            "site.costPerKWh",
            "site.costPerKwhExcludeVat",
            "site.vat",
            "site.costPerKwhExcludeVat",
            "site.currencyId",
        ],
        "units": "",
        "convert_units_func": None,
        "icon": "mdi:currency-usd",
    },
}


async def async_setup_entry(hass, entry, async_add_entities):
    """Set up the Easee sensor."""
    config = hass.data[DOMAIN]["config"]
    monitored_conditions = config.options.get(CONF_MONITORED_CONDITIONS, ["status"])

    sites: List[Site] = hass.data[DOMAIN]["sites"]

    sensors = []
    charger_data_list = []

    for site in sites:
        _LOGGER.debug("Found site: %s %s", site.id, site["name"])
        for circuit in site.get_circuits():
            _LOGGER.debug("Found circuit: %s %s", circuit.id, circuit["panelName"])
            for charger in circuit.get_chargers():
                _LOGGER.debug("Found charger: %s %s", charger.id, charger.name)
                charger_data = ChargerData(charger, circuit, site)
                charger_data_list.append(charger_data)

                for key in monitored_conditions:
                    data = SENSOR_TYPES[key]
                    _LOGGER.debug("Adding sensor: %s for charger %s", key, charger.name)
                    sensors.append(
                        ChargerSensor(
                            charger_data=charger_data,
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
                        ChargerConsumptionSensor(
                            charger, f"consumption_days_{interval}", int(interval)
                        )
                    )

    chargers_data = ChargersData(charger_data_list, sensors)

    hass.async_add_job(chargers_data.async_refresh)
    async_track_time_interval(hass, chargers_data.async_refresh, SCAN_INTERVAL)
    async_add_entities(sensors)

    # handle unsub later
    unsub = entry.add_update_listener(config_entry_update_listener)


async def config_entry_update_listener(hass, entry):
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


class ChargerData:
    def __init__(self, charger: Charger, circuit: Circuit, site: Site):
        self.charger: Charger = charger
        self.circuit: Circuit = circuit
        self.site: Site = site
        self.state: List[ChargerState] = {}
        self.config: List[ChargerConfig] = {}
        self.schedule: List[ChargerSchedule] = {}

    async def async_refresh(self, now=None):
        self.state = await self.charger.get_state()
        self.config = await self.charger.get_config()
        self.schedule = await self.charger.get_basic_charge_plan()
        _LOGGER.debug("Schedule: %s", self.schedule)


class ChargersData:
    """Representation chargers data"""

    def __init__(self, chargers: List[ChargerData], sensors: List[Any]):
        """Initialize the sensor."""
        self._chargers = chargers
        self._sensors = sensors

    async def async_refresh(self, now=None):
        """Fetch new state data for the sensors. """
        tasks = [charger.async_refresh() for charger in self._chargers]
        if tasks:
            await asyncio.wait(tasks)

        # Schedule an update for all included sensors
        for sensor in self._sensors:
            sensor.async_schedule_update_ha_state(True)


class ChargerSensor(Entity):
    """Implementation of Easee charger sensor """

    def __init__(
        self,
        charger_data: ChargerData,
        name: str,
        state_key: str,
        units: str,
        convert_units_func: Callable,
        attrs_keys: List[str],
        icon: str,
        state_func=None,
    ):
        """Initialize the sensor."""
        self.charger_data = charger_data
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
        return f"{DOMAIN}_charger_{self.charger_data.charger.id}_{self._sensor_name}"

    @property
    def unique_id(self) -> str:
        """Return a unique ID."""
        return f"{self.charger_data.charger.id}_{self._sensor_name}"

    @property
    def device_info(self) -> Dict[str, any]:
        """Return the device information."""
        return {
            "identifiers": {(DOMAIN, self.charger_data.charger.id)},
            "name": self.charger_data.charger.name,
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
            attrs = {
                "name": self.charger_data.charger.name,
                "id": self.charger_data.charger.id,
            }
            for attr_key in self._attrs_keys:
                key = attr_key
                if "site" in attr_key or "circuit" in attr_key:
                    # maybe for everything?
                    key = attr_key.replace(".", "_")
                attrs[key] = self.get_value_from_key(attr_key)

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
        value = None
        if first == "config":
            value = self.charger_data.config[second]
        elif first == "state":
            value = self.charger_data.state[second]
        elif first == "circuit":
            value = self.charger_data.circuit[second]
        elif first == "site":
            value = self.charger_data.site[second]
        elif first == "schedule":
            if self.charger_data.schedule is not None:
                value = self.charger_data.schedule[second]
        else:
            _LOGGER.error("Unknown first part of key: %s", key)
            raise IndexError("Unknown first part of key")

        if type(value) is datetime:
            value = dt.as_local(value)
        return value

    async def async_update(self):
        """Get the latest data and update the state."""
        _LOGGER.debug(
            "ChargerSensor async_update : %s %s",
            self.charger_data.charger.id,
            self._sensor_name,
        )
        try:
            self._state = self.get_value_from_key(self._state_key)
            if self._state_func is not None:
                if self._state_key.startswith("state"):
                    self._state = self._state_func(self.charger_data.state)
                if self._state_key.startswith("config"):
                    self._state = self._state_func(self.charger_data.config)
                if self._state_key.startswith("schedule"):
                    self._state = self._state_func(self.charger_data.schedule)
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
        return "kWh"

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
            "ChargerConsumptionSensor async_update : %s %s",
            self.charger.name,
            self._sensor_name,
        )
        now = datetime.now()
        self._state = await self.charger.get_consumption_between_dates(
            now - timedelta(0, 86400 * self._days), now
        )
