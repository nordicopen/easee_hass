"""
Easee charger sensor
Author: Niklas Fondberg<niklas.fondberg@gmail.com>
"""
from typing import Dict
from datetime import datetime, timedelta

from homeassistant.helpers.entity import Entity

from .entity import ChargerEntity, round_2_dec
from .const import DOMAIN

import logging

_LOGGER = logging.getLogger(__name__)

SCAN_INTERVAL = timedelta(minutes=15)


async def async_setup_entry(hass, entry, async_add_entities):
    """Setup sensor platform."""
    controller = hass.data[DOMAIN]["controller"]
    entities = controller.get_sensor_entities()

    async_add_entities(entities)


class ChargerSensor(ChargerEntity):
    """Implementation of Easee charger sensor."""

    @property
    def state(self):
        """Return status."""
        return self._state


class ChargerConsumptionSensor(Entity):
    """Implementation of Easee charger sensor."""

    def __init__(self, charger, name, days, units):
        """Initialize the sensor."""
        self.charger = charger
        self._sensor_name = name
        self._days = days
        self._state = None
        self._units = units

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
        """Return online status."""
        return round_2_dec(self._state, self._units)

    @property
    def state_attributes(self):
        """Return the state attributes."""
        return {
            "name": self.charger.name,
            "id": self.charger.id,
         }

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

class EqualizerSensor(Entity):
    """Implementation of Easee equalizer sensor."""

    def __init__(self, equalizer, name, units):
        """Initialize the sensor."""
        self.equalizer = equalizer
        self._sensor_name = name
        self._state = None
        self._units = units

    @property
    def name(self):
        """Return the name of the sensor."""
        return f"{DOMAIN}_equalizer_{self.equalizer.id}_{self._sensor_name}"

    @property
    def unique_id(self) -> str:
        """Return a unique ID."""
        return f"{self.equalizer.id}_{self._sensor_name}"

    @property
    def device_info(self) -> Dict[str, any]:
        """Return the device information."""
        return {
            "identifiers": {(DOMAIN, self.equalizer.id)},
            "name": self.equalizer["name"],
            "manufacturer": "Easee",
            "model": "Equalizer",
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
        """Return online status."""
        return round_2_dec(self._state, self._units)

    @property
    def state_attributes(self):
        """Return the state attributes."""
        return {
            "name": self.equalizer["name"],
            "id": self.equalizer.id,
            "isOnline": self.data["isOnline"],
            "softwareRelease": self.data["softwareRelease"],
            "latestFirmware": self.data["latestFirmware"],
            "localRSSI": self.data["localRSSI"],
            "rcpi": self.data["rcpi"],
            "activePowerImport": self.data["activePowerImport"],
            "activePowerExport": self.data["activePowerExport"],
            "reactivePowerImport": self.data["reactivePowerImport"],
            "reactivePowerExport": self.data["reactivePowerExport"],
            "voltageNL1": self.data["voltageNL1"],
            "voltageNL2": self.data["voltageNL2"],
            "voltageNL3": self.data["voltageNL3"],
            "voltageL1L2": self.data["voltageL1L2"],
            "voltageL1L3": self.data["voltageL1L3"],
            "voltageL2L3": self.data["voltageL2L3"],
            "currentL1": self.data["currentL1"],
            "currentL2": self.data["currentL2"],
            "currentL3": self.data["currentL3"],
            "activeEnergyImport": self.data["cumulativeActivePowerImport"],
            "activeEnergyExport": self.data["cumulativeActivePowerExport"],
            "reactiveEnergyImport": self.data["cumulativeReactivePowerImport"],
            "reactiveEnergyExport": self.data["cumulativeReactivePowerExport"],
        }

    @property
    def icon(self):
        """Icon to use in the frontend, if any."""
        return "mdi:flash"

    async def async_update(self):
        """Get the latest data and update the state."""
        _LOGGER.debug(
            "Equalizer async_update : %s %s",
            self.equalizer["name"],
            self._sensor_name,
        )
        self.data = await self.equalizer.get_state()
        self._state = self.data["activePowerImport"]
        _LOGGER.debug(
            "Equalizer state : %s",
            self._state,
        )
        
