"""Easee charger switch."""

import logging

from homeassistant.components.switch import SwitchEntity

from .const import DOMAIN
from .entity import ChargerEntity

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass, entry, async_add_entities):
    """Setup switch platform."""
    controller = hass.data[DOMAIN]["controller"]
    entities = controller.get_switch_entities()
    async_add_entities(entities)


class ChargerSwitch(ChargerEntity, SwitchEntity):
    """Easee switch class."""

    async def async_turn_on(self, **kwargs):  # pylint: disable=unused-argument
        """Turn on the switch."""
        _LOGGER.debug("%s Switch turn on" % self._entity_name)
        self.set_value_from_key(self._state_key, True)
        self._state = True
        self.async_write_ha_state()
        function_call = getattr(self.data.product, self._switch_func)
        await function_call(True)

    async def async_turn_off(self, **kwargs):  # pylint: disable=unused-argument
        """Turn off the switch."""
        _LOGGER.debug("%s Switch turn off" % self._entity_name)
        self.set_value_from_key(self._state_key, False)
        self._state = False
        self.async_write_ha_state()
        function_call = getattr(self.data.product, self._switch_func)
        await function_call(False)

    @property
    def is_on(self):
        """Return true if the switch is on."""
        _LOGGER.debug("Getting state of %s", self._entity_name)
        return self._state
