"""Sensors fed by the local OCPP connection."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    EntityCategory,
    UnitOfElectricCurrent,
    UnitOfElectricPotential,
    UnitOfEnergy,
    UnitOfPower,
    UnitOfTemperature,
    UnitOfTime,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.typing import StateType

from .configuration_entities import (
    ConfigurationKeyEntity,
    async_add_configuration_entities,
    is_read_only_key,
)
from .entity import OcppEntity
from .hub import OcppHub
from .models import (
    MEASURAND_CURRENT,
    MEASURAND_CURRENT_OFFERED,
    MEASURAND_POWER,
    MEASURAND_TEMPERATURE,
    MEASURAND_VOLTAGE,
    ChargePointState,
    Serial,
)

type SensorValue = StateType | datetime

CONNECTOR_STATUSES = [
    "available",
    "preparing",
    "charging",
    "suspendedevse",
    "suspendedev",
    "finishing",
    "reserved",
    "unavailable",
    "faulted",
]
PHASES = ("L1", "L2", "L3")


@dataclass(frozen=True, kw_only=True)
class OcppSensorEntityDescription(SensorEntityDescription):
    """Describes how a sensor reads its value from the charge point state."""

    value_fn: Callable[[ChargePointState], SensorValue]


def connector_status(state: ChargePointState) -> str | None:
    """Status in the lower-case form used as translation key."""
    return state.connector_status.lower() if state.connector_status else None


def transaction_started_at(state: ChargePointState) -> datetime | None:
    """Start of the open session."""
    return state.transaction.started_at if state.transaction else None


def transaction_id(state: ChargePointState) -> int | None:
    """Id of the open session."""
    return state.transaction.transaction_id if state.transaction else None


def last_card(state: ChargePointState) -> str | None:
    """Id of the last RFID card the charger asked about."""
    return state.last_authorization.id_tag if state.last_authorization else None


def firmware_version(state: ChargePointState) -> str | None:
    """Firmware reported in the last BootNotification."""
    return state.boot_info.firmware_version if state.boot_info else None


def phase_sensor(
    measurand: str, phase: str, key: str, device_class: SensorDeviceClass, unit: str
) -> OcppSensorEntityDescription:
    """Describe a measurand reported per phase."""
    return OcppSensorEntityDescription(
        key=f"{key}_{phase.lower()}",
        translation_key=f"{key}_{phase.lower()}",
        device_class=device_class,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=unit,
        suggested_display_precision=1,
        value_fn=lambda state: state.measurement(measurand, phase),
    )


SENSOR_DESCRIPTIONS: tuple[OcppSensorEntityDescription, ...] = (
    OcppSensorEntityDescription(
        key="status",
        device_class=SensorDeviceClass.ENUM,
        options=CONNECTOR_STATUSES,
        value_fn=connector_status,
    ),
    OcppSensorEntityDescription(
        key="power",
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfPower.WATT,
        suggested_display_precision=0,
        value_fn=lambda state: state.measurement(MEASURAND_POWER),
    ),
    OcppSensorEntityDescription(
        key="energy",
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
        native_unit_of_measurement=UnitOfEnergy.WATT_HOUR,
        suggested_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        suggested_display_precision=2,
        value_fn=lambda state: state.energy_register_wh(),
    ),
    OcppSensorEntityDescription(
        key="session_energy",
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL,
        native_unit_of_measurement=UnitOfEnergy.WATT_HOUR,
        suggested_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        suggested_display_precision=2,
        value_fn=lambda state: state.session_energy_wh(),
    ),
    OcppSensorEntityDescription(
        key="session_start",
        device_class=SensorDeviceClass.TIMESTAMP,
        value_fn=transaction_started_at,
    ),
    OcppSensorEntityDescription(
        key="current_offered",
        device_class=SensorDeviceClass.CURRENT,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfElectricCurrent.AMPERE,
        suggested_display_precision=1,
        value_fn=lambda state: state.measurement(MEASURAND_CURRENT_OFFERED),
    ),
    OcppSensorEntityDescription(
        key="charging_limit",
        device_class=SensorDeviceClass.CURRENT,
        native_unit_of_measurement=UnitOfElectricCurrent.AMPERE,
        suggested_display_precision=0,
        value_fn=lambda state: state.composite_limit_amps,
    ),
    OcppSensorEntityDescription(
        key="temperature",
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda state: state.measurement(MEASURAND_TEMPERATURE),
    ),
    *(
        phase_sensor(
            MEASURAND_CURRENT,
            phase,
            "current",
            SensorDeviceClass.CURRENT,
            UnitOfElectricCurrent.AMPERE,
        )
        for phase in PHASES
    ),
    *(
        phase_sensor(
            MEASURAND_VOLTAGE,
            phase,
            "voltage",
            SensorDeviceClass.VOLTAGE,
            UnitOfElectricPotential.VOLT,
        )
        for phase in PHASES
    ),
    OcppSensorEntityDescription(
        key="last_rfid_card",
        value_fn=last_card,
    ),
    OcppSensorEntityDescription(
        key="error_code",
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda state: state.error_code,
    ),
    OcppSensorEntityDescription(
        key="vendor_error_code",
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        value_fn=lambda state: state.vendor_error_code,
    ),
    OcppSensorEntityDescription(
        key="transaction_id",
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        value_fn=transaction_id,
    ),
    OcppSensorEntityDescription(
        key="last_message",
        device_class=SensorDeviceClass.TIMESTAMP,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        value_fn=lambda state: state.last_message_at,
    ),
    OcppSensorEntityDescription(
        key="meter_value_interval",
        device_class=SensorDeviceClass.DURATION,
        native_unit_of_measurement=UnitOfTime.SECONDS,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        value_fn=lambda state: state.meter_value_sample_interval,
    ),
    OcppSensorEntityDescription(
        key="firmware",
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        value_fn=firmware_version,
    ),
)


class OcppSensor(OcppEntity, SensorEntity):
    """A value reported by the charger via OCPP."""

    entity_description: OcppSensorEntityDescription

    @property
    def native_value(self) -> SensorValue:
        """Read the value from the live state."""
        return self.entity_description.value_fn(self.charge_point_state)


class OcppLastCardSensor(OcppSensor):
    """Shows whether the last card was accepted, so unknown cards can be added to the whitelist."""

    @property
    def extra_state_attributes(self) -> dict[str, object] | None:
        """Accepted flag and time of the last attempt."""
        attempt = self.charge_point_state.last_authorization
        if attempt is None:
            return None
        return {
            "accepted": attempt.accepted,
            "timestamp": attempt.timestamp.isoformat(),
        }


class OcppConfigurationSensor(ConfigurationKeyEntity, SensorEntity):
    """A read-only OCPP configuration key (diagnostic)."""

    description_class = SensorEntityDescription

    @property
    def native_value(self) -> str | None:
        """Current value."""
        return self.configuration_value


def async_setup_ocpp_configuration_sensors(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """One diagnostic sensor per read-only configuration key."""
    async_add_configuration_entities(
        hass, entry, async_add_entities, is_read_only_key, OcppConfigurationSensor
    )


def ocpp_sensors(hub: OcppHub, serial: Serial) -> list[OcppSensor]:
    """All OCPP sensors of one charger."""
    return [
        OcppLastCardSensor(hub, serial, description)
        if description.key == "last_rfid_card"
        else OcppSensor(hub, serial, description)
        for description in SENSOR_DESCRIPTIONS
    ]
