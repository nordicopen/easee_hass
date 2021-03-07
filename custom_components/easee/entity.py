"""
Easee Charger base entity class.
Author: Niklas Fondberg<niklas.fondberg@gmail.com>
"""
import logging
from datetime import datetime
from typing import Callable, Dict, List

from homeassistant.const import ENERGY_WATT_HOUR, POWER_WATT
from homeassistant.helpers import device_registry, entity_registry
from homeassistant.helpers.entity import Entity
from homeassistant.helpers.entity_registry import async_entries_for_device
from homeassistant.util import dt

from .const import DOMAIN, EASEE_STATUS, REASON_NO_CURRENT

_LOGGER = logging.getLogger(__name__)

""" TODO Quick fix to handle rounding: Cleanup and collapse later """


def round_to_dec(value, decimals=None, unit=None):
    """Round to selected no of decimals."""
    if unit == POWER_WATT or unit == ENERGY_WATT_HOUR:
        value = value * 1000
        decimals = None
    try:
        return round(value, decimals)
    except TypeError:
        pass
    return value


def round_2_dec(value, unit=None):
    return round_to_dec(value, 2, unit)


def round_1_dec(value, unit=None):
    return round_to_dec(value, 1, unit)


def round_0_dec(value, unit=None):
    return round_to_dec(value, None, unit)


def map_charger_status(value, unit=None):
    return EASEE_STATUS.get(value, f"unknown {value}")


def map_reason_no_current(value, unit=None):
    return REASON_NO_CURRENT.get(value, f"unknown {value}")


convert_units_funcs = {
    "round_0_dec": round_0_dec,
    "round_1_dec": round_1_dec,
    "round_2_dec": round_2_dec,
    "map_charger_status": map_charger_status,
    "map_reason_no_current": map_reason_no_current,
}


class ChargerEntity(Entity):
    """Implementation of Easee charger entity."""

    def __init__(
        self,
        controller,
        data,
        name: str,
        state_key: str,
        units: str,
        convert_units_func: Callable,
        attrs_keys: List[str],
        device_class: str,
        icon: str,
        state_func=None,
        switch_func=None,
        enabled_default=True,
    ):

        """Initialize the entity."""
        self.controller = controller
        self.data = data
        self._entity_name = name
        self._state_key = state_key
        self._units = units
        self._convert_units_func = convert_units_func
        self._attrs_keys = attrs_keys
        self._device_class = device_class
        self._icon = icon
        self._state_func = state_func
        self._state = None
        self._switch_func = switch_func
        self._enabled_default = enabled_default
        
    async def async_added_to_hass(self) -> None:
        """Entity created."""

        self.hass.data[DOMAIN]["entities"].append({self._entity_name: self.entity_id})

    async def async_will_remove_from_hass(self) -> None:
        """Disconnect object when removed."""
        if self in self.controller.sensor_entities:
            self.controller.sensor_entities.remove(self)
        if self in self.controller.binary_sensor_entities:
            self.controller.binary_sensor_entities.remove(self)
        if self in self.controller.switch_entities:
            self.controller.switch_entities.remove(self)
        if self in self.controller.equalizer_sensor_entities:
            self.controller.equalizer_sensor_entities.remove(self)
        ent_reg = await entity_registry.async_get_registry(self.hass)
        entity_entry = ent_reg.async_get(self.entity_id)

        dev_reg = await device_registry.async_get_registry(self.hass)
        device_entry = dev_reg.async_get(entity_entry.device_id)

        _LOGGER.debug("Removing _entity_name: %s", self._entity_name)
        if (
            self._entity_name in self.hass.data[DOMAIN]["entities_to_remove"]
            or self._entity_name in self.hass.data[DOMAIN]["eq_entities_to_remove"]
            or self.data.site.name in self.hass.data[DOMAIN]["sites_to_remove"]
        ):
            if len(async_entries_for_device(ent_reg, entity_entry.device_id)) == 1:
                dev_reg.async_remove_device(device_entry.id)
                return

            ent_reg.async_remove(self.entity_id)

    @property
    def entity_registry_enabled_default(self):
        return self._enabled_default

    @property
    def name(self):
        """Return the name of the entity."""
        return (
            f"{self.data.product.name} "
            + f"{self._entity_name}".capitalize().replace("_", " ")
        )

    @property
    def unique_id(self) -> str:
        """Return a unique ID."""
        return f"{self.data.product.id}_{self._entity_name}"

    @property
    def device_info(self) -> Dict[str, any]:
        """Return the device information."""
        return {
            "identifiers": {(DOMAIN, self.data.product.id)},
            "name": self.data.product.name,
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
    def state_attributes(self):
        """Return the state attributes."""
        try:
            attrs = {
                "name": self.data.product.name,
                "id": self.data.product.id,
            }
            for attr_key in self._attrs_keys:
                key = attr_key.replace(".", "_")
                if "voltage" in key.lower():
                    attrs[key] = round_0_dec(self.get_value_from_key(attr_key))
                elif "current" in key.lower():
                    attrs[key] = round_1_dec(self.get_value_from_key(attr_key))
                elif "cumulative" in key.lower():
                    attrs[key] = round_1_dec(
                        self.get_value_from_key(attr_key), self._units
                    )
                elif "power" in key.lower():
                    attrs[key] = round_1_dec(
                        self.get_value_from_key(attr_key), self._units
                    )
                else:
                    attrs[key] = self.get_value_from_key(attr_key)

            return attrs
        except IndexError:
            return {}

    @property
    def icon(self):
        """Icon to use in the frontend, if any."""
        return self._icon

    @property
    def device_class(self):
        """Device class of sensor."""
        return self._device_class

    @property
    def should_poll(self):
        """No polling needed."""
        return False

    def set_value_from_key(self, key, value):
        first, second = key.split(".")
        if first == "config":
            if self.data.config is not None:
                self.data.config[second] = value
        elif first == "state":
            if self.data.state is not None:
                self.data.state[second] = value
        elif first == "circuit":
            self.data.circuit[second] = value
        elif first == "site":
            self.data.site[second] = value
        elif first == "schedule":
            if self.data.schedule is not None:
                self.data.schedule[second] = value
        else:
            _LOGGER.error("Unknown first part of key: %s", key)
            raise IndexError("Unknown first part of key")

        return value

    def get_value_from_key(self, key):
        first, second = key.split(".")
        value = None
        if first == "config":
            value = self.data.config[second]
        elif first == "state":
            value = self.data.state[second]
        elif first == "circuit":
            value = self.data.circuit[second]
        elif first == "site":
            value = self.data.site[second]
        elif first == "schedule":
            if self.data.schedule is not None:
                value = self.data.schedule[second]
        else:
            _LOGGER.error("Unknown first part of key: %s", key)
            raise IndexError("Unknown first part of key")

        if type(value) is datetime:
            value = dt.as_local(value)
        return value

    async def async_update(self):
        """Get the latest data and update the state."""
        _LOGGER.debug(
            "Entity async_update : %s %s",
            self.data.product.id,
            self._entity_name,
        )
        try:
            self._state = self.get_value_from_key(self._state_key)
            if self._state_func is not None:
                if self._state_key.startswith("state"):
                    self._state = self._state_func(self.data.state)
                if self._state_key.startswith("config"):
                    self._state = self._state_func(self.data.config)
                if self._state_key.startswith("schedule"):
                    self._state = self._state_func(self.data.schedule)
            if self._convert_units_func is not None:
                self._state = self._convert_units_func(self._state, self._units)

        except IndexError:
            raise IndexError("Wrong key for entity: %s", self._state_key)
