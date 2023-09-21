"""Easee charger switch."""

import logging

from pyeasee.exceptions import ForbiddenServiceException

from homeassistant.components.switch import SwitchEntity

from .const import DOMAIN
from .entity import ChargerEntity

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass, entry, async_add_entities):
    """Set up switch platform."""
    controller = hass.data[DOMAIN]["controller"]
    entities = controller.get_switch_entities()
    async_add_entities(entities)
    await controller.setup_done("switch")


class ChargerSwitch(ChargerEntity, SwitchEntity):
    """Easee switch class."""

    async def async_turn_on(self, **kwargs):  # pylint: disable=unused-argument
        """Turn on the switch."""
        _LOGGER.debug("%s Switch turn on", self._entity_name)
        function_call = getattr(self.data.product, self._switch_func)
        try:
            await function_call(True)
        except ForbiddenServiceException:
            _LOGGER.error("Forbidden turn_on on switch %s", self._entity_name)
            return
        except Exception:  # pylint: disable=broad-except
            _LOGGER.error("Got server error while calling %s", self._switch_func)
            return
        self.set_value_from_key(self._state_key, True)
        self._state = True
        self.async_write_ha_state()

    async def async_turn_off(self, **kwargs):  # pylint: disable=unused-argument
        """Turn off the switch."""
        _LOGGER.debug("%s Switch turn off", self._entity_name)
        function_call = getattr(self.data.product, self._switch_func)
        try:
            await function_call(False)
        except ForbiddenServiceException:
            _LOGGER.error("Forbidden turn_off on switch %s", self._entity_name)
            return
        except Exception:  # pylint: disable=broad-except
            _LOGGER.error("Got server error while calling %s", self._switch_func)
            return
        self.set_value_from_key(self._state_key, False)
        self._state = False
        self.async_write_ha_state()

    @property
    def is_on(self):
        """Return true if the switch is on."""
        _LOGGER.debug("Getting state of %s", self._entity_name)
        return self._state
