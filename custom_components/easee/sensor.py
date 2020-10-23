"""
Easee charger sensor
Author: Niklas Fondberg<niklas.fondberg@gmail.com>
"""
from typing import Dict
from datetime import datetime, timedelta

from homeassistant.helpers import entity_registry, device_registry
from homeassistant.helpers.entity_registry import async_entries_for_device
from homeassistant.helpers.entity import Entity

from .entity import ChargerEntity, round_to_dec, round_2_dec, round_1_dec, round_0_dec
from .const import DOMAIN
from homeassistant.const import (
    POWER_KILO_WATT,
    ENERGY_KILO_WATT_HOUR,
    DEVICE_CLASS_POWER,
    DEVICE_CLASS_CURRENT,
    DEVICE_CLASS_ENERGY,
    DEVICE_CLASS_VOLTAGE,
    DEVICE_CLASS_SIGNAL_STRENGTH,
)


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

    def __init__(self, controller, charger, name, days, units):
        """Initialize the sensor."""
        self.controller = controller
        self.charger = charger
        self._sensor_name = name
        self._days = days
        self._state = None
        self._units = units

    async def async_will_remove_from_hass(self) -> None:
        """Disconnect object when removed."""
        if self in self.controller.consumption_sensor_entities:
            self.controller.consumption_sensor_entities.remove(self)
        ent_reg = await entity_registry.async_get_registry(self.hass)
        entity_entry = ent_reg.async_get(self.entity_id)

        dev_reg = await device_registry.async_get_registry(self.hass)
        device_entry = dev_reg.async_get(entity_entry.device_id)

        _LOGGER.debug(">>>>>>>>>>>>>> Removing _sensor_name: %s", self._sensor_name)
        if (self._sensor_name in self.hass.data[DOMAIN]["days_to_remove"] or
            self.charger.site["name"] in self.hass.data[DOMAIN]["sites_to_remove"]):
            if len(async_entries_for_device(ent_reg, entity_entry.device_id)) == 1:
                dev_reg.async_remove_device(device_entry.id)
                return

            ent_reg.async_remove(self.entity_id)

    @property
    def name(self):
        """Return the name of the sensor."""
        return f"{self.charger.name} " + f"{self._sensor_name}".capitalize().replace('_', ' ')

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
    def device_class(self):
        """Device class of sensor."""
        return DEVICE_CLASS_ENERGY

    @property
    def should_poll(self):
        """No polling needed."""
        return False

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


class EqualizerSensor(ChargerEntity):
    """Implementation of Easee equalizer sensor."""

    @property
    def state(self):
        """Return status."""
        return self._state

    @property
    def name(self):
        """Return the name of the entity."""
        return f"{self.charger_data.equalizer['name']} " + f"{self._entity_name}".capitalize().replace('_', ' ')

    @property
    def unique_id(self) -> str:
        """Return a unique ID."""
        return f"{self.charger_data.equalizer['name']}_{self._entity_name}"

    @property
    def device_info(self) -> Dict[str, any]:
        """Return the device information."""
        return {
            "identifiers": {(DOMAIN, self.charger_data.equalizer.id)},
            "name": self.charger_data.equalizer["name"],
            "manufacturer": "Easee",
            "model": "Equalizer",
        }

    async def async_will_remove_from_hass(self) -> None:
        """Disconnect object when removed."""
        ent_reg = await entity_registry.async_get_registry(self.hass)
        entity_entry = ent_reg.async_get(self.entity_id)

        dev_reg = await device_registry.async_get_registry(self.hass)
        device_entry = dev_reg.async_get(entity_entry.device_id)

        if (self._entity_name in self.hass.data[DOMAIN]["eq_entities_to_remove"] or
            self.charger_data.site["name"] in self.hass.data[DOMAIN]["sites_to_remove"]):
            if len(async_entries_for_device(ent_reg, entity_entry.device_id)) == 1:
                dev_reg.async_remove_device(device_entry.id)
                return

            ent_reg.async_remove(self.entity_id)

    async def async_update(self):
        """Get the latest data and update the state."""
        _LOGGER.debug(
            "EqualizerEntity async_update : %s %s",
            self.charger_data.equalizer.id,
            self._entity_name,
        )
        try:
            self._state = self.get_value_from_key(self._state_key)
            if self._state_func is not None:
                if self._state_key.startswith("state"):
                    self._state = self._state_func(self.charger_data.state)
                if self._state_key.startswith("config"):
                    self._state = self._state_func(self.charger_data.config)
            if self._convert_units_func is not None:
                self._state = self._convert_units_func(self._state, self._units)

        except IndexError:
            raise IndexError("Wrong key for entity: %s", self._state_key)

    @property
    def state_attributes(self):
        """Return the state attributes."""
        try:
            attrs = {
		"name": self.charger_data.equalizer["name"],
                "id": self.charger_data.equalizer.id,
            }
            for attr_key in self._attrs_keys:
                key = attr_key
                if "site" in attr_key or "circuit" in attr_key:
                    # maybe for everything?
                    key = attr_key.replace(".", "_")
                if "voltage" in key.lower():
                    attrs[key] = round_0_dec(self.get_value_from_key(attr_key))
                elif "current" in key.lower():
                    attrs[key] = round_1_dec(self.get_value_from_key(attr_key))
                elif "cumulative" in key.lower():
                    attrs[key] = round_1_dec(self.get_value_from_key(attr_key), self._units)
                elif "power" in key.lower():
                    attrs[key] = round_1_dec(self.get_value_from_key(attr_key), self._units)
                else:
                    attrs[key] = self.get_value_from_key(attr_key)

            return attrs
        except IndexError:
            return {}
