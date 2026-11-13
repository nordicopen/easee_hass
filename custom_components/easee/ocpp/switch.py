"""Switch entities: availability, charging and boolean configuration keys."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Any

from homeassistant.components.switch import SwitchEntity, SwitchEntityDescription
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .authorization import REMOTE_START_ID_TAG
from .charge_point import CommandFailedError, EaseeChargePoint
from .configuration_entities import (
    ConfigurationKeyEntity,
    async_add_configuration_entities,
    is_switch_key,
)
from .entity import OcppEntity
from .hub import OcppHub
from .models import ChargePointState, Serial

STATUS_UNAVAILABLE = "Unavailable"
OCPP_TRUE = "true"
OCPP_FALSE = "false"


async def make_available(charge_point: EaseeChargePoint) -> None:
    """ChangeAvailability Operative."""
    await charge_point.change_availability(operative=True)


async def make_unavailable(charge_point: EaseeChargePoint) -> None:
    """ChangeAvailability Inoperative."""
    await charge_point.change_availability(operative=False)


async def start_charging(charge_point: EaseeChargePoint) -> None:
    """RemoteStartTransaction with Home Assistant's own tag."""
    await charge_point.remote_start(REMOTE_START_ID_TAG)


async def stop_charging(charge_point: EaseeChargePoint) -> None:
    """RemoteStopTransaction of the open session."""
    await charge_point.remote_stop()


@dataclass(frozen=True, kw_only=True)
class OcppSwitchEntityDescription(SwitchEntityDescription):
    """A switch that reads the state and sends one command per direction."""

    is_on_fn: Callable[[ChargePointState], bool]
    turn_on_fn: Callable[[EaseeChargePoint], Awaitable[None]]
    turn_off_fn: Callable[[EaseeChargePoint], Awaitable[None]]


SWITCH_DESCRIPTIONS: tuple[OcppSwitchEntityDescription, ...] = (
    OcppSwitchEntityDescription(
        key="available",
        entity_category=EntityCategory.CONFIG,
        is_on_fn=lambda state: state.connector_status != STATUS_UNAVAILABLE,
        turn_on_fn=make_available,
        turn_off_fn=make_unavailable,
    ),
    OcppSwitchEntityDescription(
        key="charge",
        is_on_fn=lambda state: state.has_transaction(),
        turn_on_fn=start_charging,
        turn_off_fn=stop_charging,
    ),
)


class OcppSwitch(OcppEntity, SwitchEntity):
    """A command pair on the charger."""

    entity_description: OcppSwitchEntityDescription

    @property
    def is_on(self) -> bool:
        """Read the state."""
        return self.entity_description.is_on_fn(self.charge_point_state)

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Send the on command."""
        await self._send(self.entity_description.turn_on_fn)

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Send the off command."""
        await self._send(self.entity_description.turn_off_fn)

    async def _send(
        self, command: Callable[[EaseeChargePoint], Awaitable[None]]
    ) -> None:
        try:
            await command(self._hub.charge_point(self._serial))
        except CommandFailedError as error:
            raise HomeAssistantError(str(error)) from error


class OcppConfigurationSwitch(ConfigurationKeyEntity, SwitchEntity):
    """A boolean OCPP configuration key."""

    description_class = SwitchEntityDescription

    @property
    def is_on(self) -> bool | None:
        """Current value."""
        value = self.configuration_value
        return value.lower() == OCPP_TRUE if value is not None else None

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Write true."""
        await self._write(OCPP_TRUE)

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Write false."""
        await self._write(OCPP_FALSE)


def ocpp_switches(hub: OcppHub, serial: Serial) -> list[OcppSwitch]:
    """Create the fixed switches of one charger."""
    return [OcppSwitch(hub, serial, description) for description in SWITCH_DESCRIPTIONS]


def async_setup_ocpp_configuration_switches(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """One switch per boolean configuration key."""
    async_add_configuration_entities(
        hass, entry, async_add_entities, is_switch_key, OcppConfigurationSwitch
    )
