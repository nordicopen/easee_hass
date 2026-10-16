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


def percentage_to_brightness(percent: int | float) -> int:
    """Convert Easee percentage (0..100) to Home Assistant brightness (0..255)."""
    return round(percent * 255 / 100)


def brightness_to_percentage(brightness: int) -> int:
    """Convert Home Assistant brightness (1..255) to Easee percentage (0..100)."""
    if brightness <= 0:
        return 0
    return max(1, round(brightness * 100 / 255))


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
            percent = self.get_value_from_key("config.ledStripBrightness")
            if percent is None:
                return None
            brightness = percentage_to_brightness(percent)
            _LOGGER.debug("Brightness: %s", brightness)
            return brightness
        except (TypeError, ValueError):
            return None

    @property
    def is_on(self) -> bool | None:
        """Return on/off state."""
        b = self.brightness
        if b is None:
            return None
        return b > 0

    async def async_turn_on(self, **kwargs) -> None:
        """Turn on the light."""
        brightness = kwargs.get("brightness")
        if brightness is not None:
            percent = brightness_to_percentage(brightness)
        else:
            percent = 100

        _LOGGER.debug(
            "Turn_on on light %s, brightness_percent=%s",
            self._entity_name,
            percent,
        )
        function_call = getattr(self.data.product, self._switch_func)
        try:
            await function_call(percent)
        except ForbiddenServiceException:
            _LOGGER.error("Forbidden turn_on on light %s", self._entity_name)
            return
        except Exception:  # pylint: disable=broad-except
            _LOGGER.error("Got server error while calling %s", self._switch_func)
            return
        self.set_value_from_key(self._state_key, percent)
        self.async_write_ha_state()

        return

    async def async_turn_off(self, **kwargs) -> None:
        """Turn off the light."""
        _LOGGER.debug("Turn_off on light %s", self._entity_name)
        function_call = getattr(self.data.product, self._switch_func)
        try:
            await function_call(0)
        except ForbiddenServiceException:
            _LOGGER.error("Forbidden turn_off on light %s", self._entity_name)
            return
        except Exception:  # pylint: disable=broad-except
            _LOGGER.error("Got server error while calling %s", self._switch_func)
            return
        self.set_value_from_key(self._state_key, 0)
        self.async_write_ha_state()

        return
