"""Easee charger binary sensor."""

from dataclasses import dataclass
from enum import StrEnum
import logging
from typing import Final

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
    BinarySensorEntityDescription,
)
from homeassistant.helpers.entity import DeviceInfo, EntityCategory

from .const import DOMAIN, MANUFACTURER, MODEL_EQUALIZER
from .controller import Controller
from .entity import ChargerEntity

_LOGGER = logging.getLogger(__name__)


class EaseeType(StrEnum):
    """Define Easee device classes."""

    CHARGER = "charger"
    EQUALIZER = "equalizer"


@dataclass
class EaseeBinarySensorDescription(BinarySensorEntityDescription):
    """Class describing Easee binary sensor entities."""


@dataclass
class EaseeBinarySensorDefinition:
    """Class for defining binary sensor entities."""

    types: tuple[EaseeType, ...]
    description: EaseeBinarySensorDescription = None


BINARY_SENSORS: Final[tuple[EaseeBinarySensorDefinition, ...]] = (
    EaseeBinarySensorDefinition(
        types=[EaseeType.CHARGER],
        description=EaseeBinarySensorDescription(
            key="state.cableLocked",
            entity_category=EntityCategory.DIAGNOSTIC,
            device_class=BinarySensorDeviceClass.LOCK,
            translation_key="cable_locked",
        ),
    )
)


async def async_setup_entry(hass, entry, async_add_entities):
    """Set up binary sensor platform."""
    controller: Controller = hass.data[DOMAIN]["controller"]
    entities = controller.get_binary_sensor_entities()
    async_add_entities(entities)
    await controller.setup_done("binary_sensor")


class ChargerBinarySensor(ChargerEntity, BinarySensorEntity):
    """Easee charger binary sensor class."""

    @property
    def is_on(self):
        """Return true if the binary sensor is on."""
        _LOGGER.debug("Getting state of %s", self._entity_name)
        return self._state


class EqualizerBinarySensor(ChargerEntity, BinarySensorEntity):
    """Easee equalizer binary sensor class."""

    @property
    def is_on(self):
        """Return true if the binary sensor is on."""
        _LOGGER.debug("Getting state of %s", self._entity_name)
        return self._state

    @property
    def device_info(self):
        """Return the device information."""
        return DeviceInfo(
            identifiers={(DOMAIN, self.data.product.id)},
            serial_number=self.data.product.id,
            name=self.data.product.name,
            manufacturer=MANUFACTURER,
            model=MODEL_EQUALIZER,
            configuration_url=f"https://easee.cloud/mypage/products/{self.data.product.id}",
        )
