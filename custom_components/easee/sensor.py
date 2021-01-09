"""
Easee charger sensor
Author: Niklas Fondberg<niklas.fondberg@gmail.com>
"""
import logging
from datetime import date, datetime, timedelta
from typing import Dict

from homeassistant.const import DEVICE_CLASS_ENERGY
from homeassistant.helpers import device_registry, entity_registry
from homeassistant.helpers.entity import Entity
from homeassistant.helpers.entity_registry import async_entries_for_device

from .const import DOMAIN
from .entity import ChargerEntity, round_0_dec, round_1_dec, round_2_dec

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

class EqualizerSensor(ChargerEntity):
    """Implementation of Easee equalizer sensor."""

    @property
    def state(self):
        """Return status."""
        return self._state

    @property
    def name(self):
        """Return the name of the entity."""
        return (
            f"{self.charger_data.equalizer['name']} "
            + f"{self._entity_name}".capitalize().replace("_", " ")
        )

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
