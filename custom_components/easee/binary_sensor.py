"""Easee charger binary sensor."""

from homeassistant.components.binary_sensor import BinarySensorEntity

from .entity import ChargerEntity
from .const import DOMAIN
import logging

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass, entry, async_add_entities):
    """Setup binary sensor platform."""
    controller = hass.data[DOMAIN]["controller"]
    entities = controller.get_binary_sensor_entities()
    async_add_entities(entities)


class ChargerBinarySensor(ChargerEntity, BinarySensorEntity):
    """Easee charger binary sensor class."""

    @property
    def is_on(self):
        """Return true if the binary sensor is on."""
        _LOGGER.debug("Getting state of %s" % self._entity_name)
        return self._state
