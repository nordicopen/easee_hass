"""Easee charger light entity."""

import logging

from pyeasee.exceptions import ForbiddenServiceException

from homeassistant.components.light import ColorMode, LightEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN
from .entity import ChargerEntity

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up light platform."""
    controller = hass.data[DOMAIN]["controller"]
    entities = controller.get_light_entities()
    async_add_entities(entities)
    await controller.async_setup_done("light")


class ChargerLight(ChargerEntity, LightEntity):
    """Easee light class."""

    _attr_color_mode = ColorMode.BRIGHTNESS
    _attr_supported_color_modes = [ColorMode.BRIGHTNESS]

    @property
    def brightness(self) -> int | None:
        """Return brightness value 1..255."""
        try:
            brightness = self.get_value_from_key("config.ledStripBrightness")
            _LOGGER.debug("Brightness: %s", int(brightness * 255 / 100))
            return round(brightness * 255 / 100)
        except TypeError:
            return None

    @property
    def is_on(self) -> bool | None:
        """Return on/off state."""
        return True

    async def async_turn_on(self, **kwargs) -> None:
        """Turn on the light."""
        brightness = round(kwargs.get("brightness", 255) * 100 / 255)
        _LOGGER.debug(
            "Turn_on on light %s, brightness=%s",
            self._entity_name,
            brightness,
        )
        function_call = getattr(self.data.product, self._switch_func)
        try:
            await function_call(brightness)
        except ForbiddenServiceException:
            _LOGGER.error("Forbidden turn_on on light %s", self._entity_name)
            return
        except Exception:  # pylint: disable=broad-except
            _LOGGER.error("Got server error while calling %s", self._switch_func)
            return
        self.set_value_from_key(self._state_key, True)
        # self._state = True
        # self.async_write_ha_state()

        return

    async def async_turn_off(self, **kwargs) -> None:
        """Turn off the light."""
        return
