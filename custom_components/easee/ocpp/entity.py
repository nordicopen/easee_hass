"""Base class for entities fed by the local OCPP connection."""

from __future__ import annotations

from homeassistant.core import callback
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity import Entity, EntityDescription

from ..const import DOMAIN
from .const import OCPP_UNIQUE_ID_MARKER
from .hub import OcppHub, signal_state_updated
from .models import ChargePointState, Serial


def ocpp_unique_id(serial: Serial, key: str) -> str:
    """Return a unique id that never collides with the cloud entities of the same charger."""
    return f"{serial}{OCPP_UNIQUE_ID_MARKER}{key}"


class OcppEntity(Entity):
    """Attaches to the existing device of the charger and refreshes on every OCPP update."""

    _attr_has_entity_name = True
    _attr_should_poll = False

    def __init__(
        self, hub: OcppHub, serial: Serial, description: EntityDescription
    ) -> None:
        """Bind the entity to one charger."""
        self._hub = hub
        self._serial = serial
        self.entity_description = description
        self._attr_unique_id = ocpp_unique_id(serial, description.key)
        # Prefixed so the OCPP texts never clash with the cloud entities' translations.
        self._attr_translation_key = (
            f"ocpp_{description.translation_key or description.key}"
        )
        self._attr_device_info = DeviceInfo(identifiers={(DOMAIN, serial)})

    @property
    def charge_point_state(self) -> ChargePointState:
        """Live OCPP state of the charger."""
        return self._hub.state(self._serial)

    @property
    def available(self) -> bool:
        """Values are only meaningful while the charger is connected."""
        return self._hub.is_connected(self._serial)

    async def async_added_to_hass(self) -> None:
        """Follow state changes of the charger."""
        self.async_on_remove(
            async_dispatcher_connect(
                self.hass,
                signal_state_updated(self._serial),
                self._handle_state_updated,
            )
        )

    @callback
    def _handle_state_updated(self) -> None:
        self.async_write_ha_state()
