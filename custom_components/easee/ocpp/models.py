"""State of a locally connected OCPP charge point."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta

type Serial = str
type IdTag = str
type Measurand = str
type Phase = str
type MeasurementKey = tuple[Measurand, Phase | None]

MEASURAND_ENERGY_REGISTER = "Energy.Active.Import.Register"
MEASURAND_POWER = "Power.Active.Import"
MEASURAND_CURRENT = "Current.Import"
MEASURAND_CURRENT_OFFERED = "Current.Offered"
MEASURAND_VOLTAGE = "Voltage"
MEASURAND_TEMPERATURE = "Temperature"

STATUS_CHARGING = "Charging"


@dataclass(frozen=True)
class Measurement:
    """A sampled value, normalised to W, Wh, A, V or °C."""

    value: float
    timestamp: datetime


@dataclass(frozen=True)
class BootInfo:
    """What the charge point reported in its BootNotification."""

    vendor: str
    model: str
    firmware_version: str | None
    serial_number: str | None


@dataclass(frozen=True)
class Transaction:
    """A charging session as seen by the central system."""

    transaction_id: int
    id_tag: IdTag
    meter_start_wh: float
    started_at: datetime


@dataclass(frozen=True)
class ConfigurationValue:
    """One key of the charge point configuration (GetConfiguration)."""

    value: str | None
    readonly: bool

    def is_boolean(self) -> bool:
        """Return True if the value looks like an OCPP boolean."""
        return self.value is not None and self.value.lower() in {"true", "false"}

    def is_integer(self) -> bool:
        """Return True if the value is a whole number."""
        return self.value is not None and self.value.lstrip("-").isdigit()


@dataclass(frozen=True)
class AuthorizationAttempt:
    """The last RFID card the charge point asked about."""

    id_tag: IdTag
    accepted: bool
    timestamp: datetime


@dataclass
class ChargePointState:
    """Everything the central system knows about one charge point."""

    serial: Serial
    connected: bool = False
    connected_since: datetime | None = None
    disconnected_since: datetime | None = None
    authentication_failures: int = 0
    last_message_at: datetime | None = None
    boot_info: BootInfo | None = None
    connector_status: str | None = None
    error_code: str | None = None
    vendor_error_code: str | None = None
    status_info: str | None = None
    measurements: dict[MeasurementKey, Measurement] = field(default_factory=dict)
    transaction: Transaction | None = None
    last_transaction_energy_wh: float | None = None
    last_authorization: AuthorizationAttempt | None = None
    configuration: dict[str, ConfigurationValue] = field(default_factory=dict)
    unsupported_configuration_keys: set[str] = field(default_factory=set)
    meter_value_sample_interval: int | None = None
    composite_limit_amps: float | None = None

    def disconnected_longer_than(self, duration: timedelta, now: datetime) -> bool:
        """Return True if the charger has been offline for at least duration."""
        return (
            not self.connected
            and self.disconnected_since is not None
            and now - self.disconnected_since >= duration
        )

    def has_transaction(self) -> bool:
        """Return True while a charging session is open."""
        return self.transaction is not None

    def is_charging(self) -> bool:
        """Return True if the connector reports that energy flows."""
        return self.connector_status == STATUS_CHARGING

    def measurement(
        self, measurand: Measurand, phase: Phase | None = None
    ) -> float | None:
        """Return the latest value of a measurand, or None if never reported."""
        sample = self.measurements.get((measurand, phase))
        return sample.value if sample is not None else None

    def energy_register_wh(self) -> float | None:
        """Return the lifetime energy meter reading."""
        return self.measurement(MEASURAND_ENERGY_REGISTER)

    def session_energy_wh(self) -> float | None:
        """Energy of the open session, or of the last finished one."""
        if self.transaction is None:
            return self.last_transaction_energy_wh
        register = self.energy_register_wh()
        if register is None:
            return None
        return max(register - self.transaction.meter_start_wh, 0.0)

    def session_duration(self, now: datetime) -> timedelta | None:
        """Return how long the open session has been running."""
        if self.transaction is None:
            return None
        return now - self.transaction.started_at

    def configuration_value(self, key: str) -> str | None:
        """Return a configuration value, or None if unknown."""
        entry = self.configuration.get(key)
        return entry.value if entry is not None else None

    def supports_configuration_key(self, key: str) -> bool:
        """Return True if the charge point reported this key."""
        return key in self.configuration
