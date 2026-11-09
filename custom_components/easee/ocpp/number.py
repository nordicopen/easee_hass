"""Number entities: charger current limit and numeric configuration keys."""

from __future__ import annotations

from homeassistant.components.number import (
    NumberDeviceClass,
    NumberEntity,
    NumberEntityDescription,
    NumberMode,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import PERCENTAGE, UnitOfElectricCurrent, UnitOfTime
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .charge_point import CommandFailedError
from .configuration_entities import (
    ConfigurationKeyEntity,
    async_add_configuration_entities,
    is_number_key,
)
from .entity import OcppEntity
from .hub import OcppHub
from .models import Serial

MAX_CURRENT_AMPS = 32
GENERIC_KEY_MAXIMUM = 86_400

# Known keys get a sensible range and unit; unknown numeric keys fall back to 0..86400.
KNOWN_KEY_RANGES: dict[str, tuple[int, int, str | None]] = {
    "LightIntensity": (0, 100, PERCENTAGE),
    "HeartbeatInterval": (0, GENERIC_KEY_MAXIMUM, UnitOfTime.SECONDS),
    "MeterValueSampleInterval": (0, 3600, UnitOfTime.SECONDS),
    "ClockAlignedDataInterval": (0, GENERIC_KEY_MAXIMUM, UnitOfTime.SECONDS),
}

MAX_CURRENT_DESCRIPTION = NumberEntityDescription(
    key="max_current",
    device_class=NumberDeviceClass.CURRENT,
    native_unit_of_measurement=UnitOfElectricCurrent.AMPERE,
    native_min_value=0,
    native_max_value=MAX_CURRENT_AMPS,
    native_step=1,
    mode=NumberMode.SLIDER,
)


class OcppMaxCurrentNumber(OcppEntity, NumberEntity):
    """Charger limit (ChargePointMaxProfile); 0 A pauses charging. Re-sent after every reconnect."""

    @property
    def native_value(self) -> float:
        """The limit HA keeps in force."""
        return self._hub.max_current(self._serial)

    async def async_set_native_value(self, value: float) -> None:
        """Send the new limit to the charger."""
        try:
            await self._hub.async_set_max_current(self._serial, value)
        except CommandFailedError as error:
            raise HomeAssistantError(str(error)) from error


class OcppConfigurationNumber(ConfigurationKeyEntity, NumberEntity):
    """A numeric OCPP configuration key."""

    description_class = NumberEntityDescription
    _attr_mode = NumberMode.BOX
    _attr_native_step = 1

    def __init__(self, hub: OcppHub, serial: Serial, key: str) -> None:
        """Apply the known range of the key."""
        super().__init__(hub, serial, key)
        minimum, maximum, unit = KNOWN_KEY_RANGES.get(
            key, (0, GENERIC_KEY_MAXIMUM, None)
        )
        self._attr_native_min_value = minimum
        self._attr_native_max_value = maximum
        self._attr_native_unit_of_measurement = unit

    @property
    def native_value(self) -> float | None:
        """Current value."""
        value = self.configuration_value
        return float(value) if value is not None else None

    async def async_set_native_value(self, value: float) -> None:
        """Write the key."""
        await self._write(str(int(value)))


def ocpp_numbers(hub: OcppHub, serial: Serial) -> list[NumberEntity]:
    """Create the fixed number entities of one charger."""
    return [OcppMaxCurrentNumber(hub, serial, MAX_CURRENT_DESCRIPTION)]


def async_setup_ocpp_numbers(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Add one number per numeric configuration key."""
    async_add_configuration_entities(
        hass, entry, async_add_entities, is_number_key, OcppConfigurationNumber
    )
