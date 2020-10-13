"""Easee charger switch."""

from homeassistant.components.switch import SwitchEntity

from .entity import ChargerEntity
from .const import DOMAIN
import logging

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
        function_call = getattr(self.charger_data.charger, self._switch_func)
        await function_call(True)
        await self.controller.refresh_sites_state()
        await self.async_update()

    async def async_turn_off(self, **kwargs):  # pylint: disable=unused-argument
        """Turn off the switch."""
        _LOGGER.debug("%s Switch turn off" % self._entity_name)
        function_call = getattr(self.charger_data.charger, self._switch_func)
        await function_call(False)
        await self.controller.refresh_sites_state()
        await self.async_update()

    @property
    def is_on(self):
        """Return true if the switch is on."""
        _LOGGER.debug("Getting state of %s" % self._entity_name)
        return self._state
