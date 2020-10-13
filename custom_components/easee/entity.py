"""
Easee Charger base entity class.
Author: Niklas Fondberg<niklas.fondberg@gmail.com>
"""
from typing import Callable, Dict, List
from datetime import datetime

from homeassistant.helpers import entity_registry
from homeassistant.helpers.entity import Entity
from homeassistant.util import dt

from .const import DOMAIN
import logging

_LOGGER = logging.getLogger(__name__)


def round_2_dec(value, unit=None):
    """Round to two decimals."""
    if unit == "W" or unit == "Wh":
        value = value * 1000
    return round(value, 2)


convert_units_funcs = {
    "round_2_dec": round_2_dec,
}


class ChargerEntity(Entity):
    """Implementation of Easee charger entity."""

    def __init__(
        self,
        controller,
        charger_data,
        name: str,
        state_key: str,
        units: str,
        convert_units_func: Callable,
        attrs_keys: List[str],
        icon: str,
        state_func=None,
        switch_func=None,
    ):

        """Initialize the entity."""
        self.controller = controller
        self.charger_data = charger_data
        self._entity_name = name
        self._state_key = state_key
        self._units = units
        self._convert_units_func = convert_units_func
        self._attrs_keys = attrs_keys
        self._icon = icon
        self._state_func = state_func
        self._state = None
        self._switch_func = switch_func

    async def async_added_to_hass(self) -> None:
        """Entity created."""
        self.hass.data[DOMAIN]["entities"].append({self._entity_name: self.entity_id})

    async def async_will_remove_from_hass(self) -> None:
        """Disconnect object when removed."""
        ent_reg = await entity_registry.async_get_registry(self.hass)
        if self._entity_name in self.hass.data[DOMAIN]["entities_to_remove"]:
            ent_reg.async_remove(self.entity_id)

    @property
    def name(self):
        """Return the name of the entity."""
        return f"{DOMAIN}_charger_{self.charger_data.charger.id}_{self._entity_name}"

    @property
    def unique_id(self) -> str:
        """Return a unique ID."""
        return f"{self.charger_data.charger.id}_{self._entity_name}"

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
            "ChargerEntity async_update : %s %s",
            self.charger_data.charger.id,
            self._entity_name,
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
                self._state = self._convert_units_func(self._state, self._units)

        except IndexError:
            raise IndexError("Wrong key for entity: %s", self._state_key)
