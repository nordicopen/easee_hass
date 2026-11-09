"""Button entities: reset, unlock, refresh and learning an RFID card."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass

from homeassistant.components.button import (
    ButtonDeviceClass,
    ButtonEntity,
    ButtonEntityDescription,
)
from homeassistant.const import EntityCategory
from homeassistant.exceptions import HomeAssistantError

from .authorization import RfidAuthorizer
from .charge_point import CommandFailedError
from .entity import OcppEntity
from .hub import OcppHub
from .models import Serial


async def soft_reset(hub: OcppHub, serial: Serial) -> None:
    """Restart the charger software."""
    await hub.charge_point(serial).reset(hard=False)


async def hard_reset(hub: OcppHub, serial: Serial) -> None:
    """Reboot the charger."""
    await hub.charge_point(serial).reset(hard=True)


async def unlock_connector(hub: OcppHub, serial: Serial) -> None:
    """Release the cable."""
    await hub.charge_point(serial).unlock_connector()


async def refresh(hub: OcppHub, serial: Serial) -> None:
    """Ask for status, meter values, limit and configuration now."""
    await hub.async_refresh(serial)


async def learn_rfid_card(hub: OcppHub, serial: Serial) -> None:
    """Accept the next unknown card and add it to the whitelist."""
    if not isinstance(hub.authorizer, RfidAuthorizer):
        raise HomeAssistantError("Learning RFID cards is not available")
    hub.authorizer.start_learning()


@dataclass(frozen=True, kw_only=True)
class OcppButtonEntityDescription(ButtonEntityDescription):
    """A button that runs one command."""

    press_fn: Callable[[OcppHub, Serial], Awaitable[None]]
    needs_connection: bool = True


BUTTON_DESCRIPTIONS: tuple[OcppButtonEntityDescription, ...] = (
    OcppButtonEntityDescription(
        key="soft_reset",
        device_class=ButtonDeviceClass.RESTART,
        entity_category=EntityCategory.CONFIG,
        press_fn=soft_reset,
    ),
    OcppButtonEntityDescription(
        key="hard_reset",
        device_class=ButtonDeviceClass.RESTART,
        entity_category=EntityCategory.CONFIG,
        entity_registry_enabled_default=False,
        press_fn=hard_reset,
    ),
    OcppButtonEntityDescription(key="unlock", press_fn=unlock_connector),
    OcppButtonEntityDescription(
        key="refresh",
        device_class=ButtonDeviceClass.UPDATE,
        entity_category=EntityCategory.DIAGNOSTIC,
        press_fn=refresh,
    ),
    OcppButtonEntityDescription(
        key="learn_rfid",
        entity_category=EntityCategory.CONFIG,
        press_fn=learn_rfid_card,
        needs_connection=False,
    ),
)


class OcppButton(OcppEntity, ButtonEntity):
    """Runs a command on the charger."""

    entity_description: OcppButtonEntityDescription

    @property
    def available(self) -> bool:
        """Learning works without connection; the charger asks once it is back."""
        return not self.entity_description.needs_connection or super().available

    async def async_press(self) -> None:
        """Run the command."""
        try:
            await self.entity_description.press_fn(self._hub, self._serial)
        except CommandFailedError as error:
            raise HomeAssistantError(str(error)) from error


def ocpp_buttons(hub: OcppHub, serial: Serial) -> list[OcppButton]:
    """All buttons of one charger."""
    return [OcppButton(hub, serial, description) for description in BUTTON_DESCRIPTIONS]
