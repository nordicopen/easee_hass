"""Easee charger button entity."""

import logging

from pyeasee.exceptions import ForbiddenServiceException

from homeassistant.components.button import ButtonEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import DOMAIN
from .entity import ChargerEntity
from .ocpp import async_add_ocpp_entities
from .ocpp.button import ocpp_buttons

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddConfigEntryEntitiesCallback
) -> None:
    """Set up button platform."""
    controller = hass.data[DOMAIN]["controller"]
    entities = controller.get_button_entities()
    async_add_entities(entities)
    async_add_ocpp_entities(hass, async_add_entities, ocpp_buttons)
    await controller.async_setup_done("button")


class ChargerButton(ChargerEntity, ButtonEntity):
    """Easee button class."""

    async def async_press(self) -> None:
        """Press the button."""
        _LOGGER.debug("%s Button press", self._entity_name)
        function_call = getattr(self.data.product, self._switch_func)
        try:
            await function_call()
        except ForbiddenServiceException:
            _LOGGER.error("Forbidden to press the button %s", self._entity_name)
            return
        except Exception:  # pylint: disable=broad-except
            _LOGGER.error("Got server error while calling %s", self._switch_func)
            return
