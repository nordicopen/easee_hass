"""
Easee charger sensor
Author: Niklas Fondberg<niklas.fondberg@gmail.com>
"""

import logging
from datetime import timedelta
from typing import Dict

from homeassistant.components.sensor import SensorEntity

from .const import DOMAIN
from .entity import ChargerEntity

_LOGGER = logging.getLogger(__name__)

SCAN_INTERVAL = timedelta(minutes=15)


async def async_setup_entry(hass, entry, async_add_entities):
    """Setup sensor platform."""
    controller = hass.data[DOMAIN]["controller"]
    entities = controller.get_sensor_entities()
    async_add_entities(entities)
    controller.setup_done("sensor")


class ChargerSensor(ChargerEntity, SensorEntity):
    """Implementation of Easee charger sensor."""

    @property
    def state(self):
        """Return status."""
        return self._state


class EqualizerSensor(ChargerEntity, SensorEntity):
    """Implementation of Easee equalizer sensor."""

    @property
    def state(self):
        """Return status."""
        return self._state

    @property
    def device_info(self) -> Dict[str, any]:
        """Return the device information."""
        return {
            "identifiers": {(DOMAIN, self.data.product.id)},
            "name": self.data.product.name,
            "manufacturer": "Easee",
            "model": "Equalizer",
            "configuration_url": f"https://easee.cloud/mypage/products/{self.data.product.id}",
        }
