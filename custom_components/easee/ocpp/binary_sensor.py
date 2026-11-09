"""Binary sensors fed by the local OCPP connection."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
    BinarySensorEntityDescription,
)
from homeassistant.const import EntityCategory

from .entity import OcppEntity
from .hub import OcppHub
from .models import ChargePointState, Serial


@dataclass(frozen=True, kw_only=True)
class OcppBinarySensorEntityDescription(BinarySensorEntityDescription):
    """Describes how a binary sensor reads the charge point state."""

    is_on_fn: Callable[[ChargePointState], bool]
    available_while_disconnected: bool = False


BINARY_SENSOR_DESCRIPTIONS: tuple[OcppBinarySensorEntityDescription, ...] = (
    OcppBinarySensorEntityDescription(
        key="connected",
        device_class=BinarySensorDeviceClass.CONNECTIVITY,
        entity_category=EntityCategory.DIAGNOSTIC,
        is_on_fn=lambda state: state.connected,
        available_while_disconnected=True,
    ),
    OcppBinarySensorEntityDescription(
        key="transaction",
        device_class=BinarySensorDeviceClass.RUNNING,
        is_on_fn=lambda state: state.has_transaction(),
    ),
    OcppBinarySensorEntityDescription(
        key="charging",
        device_class=BinarySensorDeviceClass.BATTERY_CHARGING,
        is_on_fn=lambda state: state.is_charging(),
    ),
)


class OcppBinarySensor(OcppEntity, BinarySensorEntity):
    """An on/off state reported by the charger via OCPP."""

    entity_description: OcppBinarySensorEntityDescription

    @property
    def available(self) -> bool:
        """The connectivity sensor must stay available to show the disconnect."""
        return self.entity_description.available_while_disconnected or super().available

    @property
    def is_on(self) -> bool:
        """Read the value from the live state."""
        return self.entity_description.is_on_fn(self.charge_point_state)


def ocpp_binary_sensors(hub: OcppHub, serial: Serial) -> list[OcppBinarySensor]:
    """All OCPP binary sensors of one charger."""
    return [
        OcppBinarySensor(hub, serial, description)
        for description in BINARY_SENSOR_DESCRIPTIONS
    ]
