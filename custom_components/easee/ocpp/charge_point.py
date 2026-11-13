"""One Easee charger connected to Home Assistant via OCPP 1.6J."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime, timedelta
from decimal import Decimal
import logging
from typing import Any, Protocol

from ocpp.exceptions import OCPPError
from ocpp.routing import after, on
from ocpp.v16 import ChargePoint, call, call_result
from ocpp.v16.datatypes import (
    ChargingProfile,
    ChargingSchedule,
    ChargingSchedulePeriod,
    IdTagInfo,
)
from ocpp.v16.enums import (
    Action,
    AuthorizationStatus,
    AvailabilityType,
    ChargingProfileKindType,
    ChargingProfilePurposeType,
    ChargingRateUnitType,
    MessageTrigger,
    RegistrationStatus,
    ResetType,
    UpdateType,
)

from homeassistant.util import dt as dt_util

from .const import (
    CHARGE_POINT_MAX_PROFILE_ID,
    CHARGE_POINT_MAX_PROFILE_STACK_LEVEL,
    CONNECTOR_ID_CHARGE_POINT,
    CONNECTOR_ID_VEHICLE,
    CONTROL_LIMIT_PROFILE_ID,
    CONTROL_LIMIT_STACK_LEVEL,
    HEARTBEAT_INTERVAL,
    RESPONSE_TIMEOUT,
    TX_DEFAULT_PROFILE_ID,
    TX_DEFAULT_PROFILE_STACK_LEVEL,
)
from .meter_values import parse_meter_values, parse_timestamp
from .models import (
    AuthorizationAttempt,
    BootInfo,
    ChargePointState,
    ConfigurationValue,
    IdTag,
    Transaction,
)

_LOGGER = logging.getLogger(__name__)

ACCEPTED = "Accepted"
# Absolute profiles start slightly in the past so clock skew between HA and the charger does no harm.
SCHEDULE_START_LEAD = timedelta(seconds=10)


@dataclass(frozen=True)
class ProfileSlot:
    """Where a kind of charging profile lives; a fixed id and stack level replace older ones."""

    profile_id: int
    stack_level: int
    purpose: ChargingProfilePurposeType
    connector_id: int


MAX_CURRENT_SLOT = ProfileSlot(
    CHARGE_POINT_MAX_PROFILE_ID,
    CHARGE_POINT_MAX_PROFILE_STACK_LEVEL,
    ChargingProfilePurposeType.charge_point_max_profile,
    CONNECTOR_ID_CHARGE_POINT,
)
CONTROL_LIMIT_SLOT = ProfileSlot(
    CONTROL_LIMIT_PROFILE_ID,
    CONTROL_LIMIT_STACK_LEVEL,
    ChargingProfilePurposeType.charge_point_max_profile,
    CONNECTOR_ID_CHARGE_POINT,
)
TX_DEFAULT_SLOT = ProfileSlot(
    TX_DEFAULT_PROFILE_ID,
    TX_DEFAULT_PROFILE_STACK_LEVEL,
    ChargingProfilePurposeType.tx_default_profile,
    CONNECTOR_ID_VEHICLE,
)


class CommandFailedError(Exception):
    """The charge point rejected a command or did not answer."""


class IdTagAuthorizer(Protocol):
    """Decides whether an RFID card may start charging."""

    def is_allowed(self, serial: str, id_tag: IdTag) -> bool:
        """Return True if the card may charge at this charger."""


class OcppConnection(Protocol):
    """Transport the ocpp library reads from and writes to."""

    async def recv(self) -> str:
        """Return the next text frame."""

    async def send(self, message: str) -> None:
        """Send one text frame."""

    async def close(self) -> None:
        """Close the transport and wake its receiver."""


def ocpp_timestamp(moment: datetime) -> str:
    """Format a timestamp as Easee expects it: UTC with a trailing Z."""
    return dt_util.as_utc(moment).isoformat(timespec="seconds").replace("+00:00", "Z")


def new_transaction_id(now: datetime) -> int:
    """Return a transaction id that stays unique across restarts of Home Assistant."""
    return int(now.timestamp()) % 2**31


def without_decimals(payload: Any) -> Any:
    """Convert the Decimals the ocpp library parses into plain numbers for HA's JSON responses."""
    if isinstance(payload, Decimal):
        return float(payload)
    if isinstance(payload, dict):
        return {key: without_decimals(value) for key, value in payload.items()}
    if isinstance(payload, list):
        return [without_decimals(value) for value in payload]
    return payload


def is_accepted(status: Any) -> bool:
    """Return True if an OCPP status field means success."""
    return str(status) == ACCEPTED


class EaseeChargePoint(ChargePoint):
    """Central system side of one charge point connection."""

    def __init__(
        self,
        state: ChargePointState,
        connection: OcppConnection,
        authorizer: IdTagAuthorizer,
        on_state_changed: Callable[[], None],
        on_boot: Callable[[], None],
    ) -> None:
        """Bind the connection to the shared state of this charge point."""
        super().__init__(
            state.serial, connection, response_timeout=RESPONSE_TIMEOUT.total_seconds()
        )
        self.state = state
        self._authorizer = authorizer
        self._on_state_changed = on_state_changed
        self._on_boot = on_boot

    async def route_message(self, raw_msg: str) -> None:
        """Remember when the charger last spoke, then route the message."""
        self.state.last_message_at = dt_util.utcnow()
        await super().route_message(raw_msg)

    @on(Action.boot_notification)
    def on_boot_notification(
        self, charge_point_vendor: str, charge_point_model: str, **kwargs: Any
    ) -> call_result.BootNotification:
        """Accept the charger and remember what it is."""
        self.state.boot_info = BootInfo(
            vendor=charge_point_vendor,
            model=charge_point_model,
            firmware_version=kwargs.get("firmware_version"),
            serial_number=kwargs.get("charge_point_serial_number"),
        )
        self._on_state_changed()
        return call_result.BootNotification(
            current_time=ocpp_timestamp(dt_util.utcnow()),
            interval=int(HEARTBEAT_INTERVAL.total_seconds()),
            status=RegistrationStatus.accepted,
        )

    @after(Action.boot_notification)
    def after_boot_notification(self, **kwargs: Any) -> None:
        """Configure the charger once it has been accepted."""
        self._on_boot()

    @on(Action.heartbeat)
    def on_heartbeat(self, **kwargs: Any) -> call_result.Heartbeat:
        """Answer with the current time."""
        return call_result.Heartbeat(current_time=ocpp_timestamp(dt_util.utcnow()))

    @on(Action.status_notification)
    def on_status_notification(
        self, connector_id: int, error_code: str, status: str, **kwargs: Any
    ) -> call_result.StatusNotification:
        """Track the vehicle connector; connector 0 only matters while nothing else is known."""
        concerns_vehicle = connector_id == CONNECTOR_ID_VEHICLE
        nothing_known_yet = self.state.connector_status is None
        if concerns_vehicle or nothing_known_yet:
            self.state.connector_status = status
            self.state.error_code = error_code
            self.state.vendor_error_code = kwargs.get("vendor_error_code")
            self.state.status_info = kwargs.get("info")
            self._on_state_changed()
        return call_result.StatusNotification()

    @on(Action.meter_values)
    def on_meter_values(
        self, connector_id: int, meter_value: list[dict[str, Any]], **kwargs: Any
    ) -> call_result.MeterValues:
        """Store the newest measurements."""
        self.state.measurements.update(parse_meter_values(meter_value))
        self._on_state_changed()
        return call_result.MeterValues()

    @on(Action.authorize)
    def on_authorize(self, id_tag: str, **kwargs: Any) -> call_result.Authorize:
        """Answer from the RFID whitelist."""
        return call_result.Authorize(id_tag_info=self._authorize(id_tag))

    @on(Action.start_transaction)
    def on_start_transaction(
        self,
        connector_id: int,
        id_tag: str,
        meter_start: int,
        timestamp: str,
        **kwargs: Any,
    ) -> call_result.StartTransaction:
        """Open a session; the charger stops it again if the card is rejected."""
        id_tag_info = self._authorize(id_tag)
        now = dt_util.utcnow()
        transaction = Transaction(
            transaction_id=new_transaction_id(now),
            id_tag=id_tag,
            meter_start_wh=float(meter_start),
            started_at=parse_timestamp(timestamp),
        )
        if is_accepted(id_tag_info.status):
            self.state.transaction = transaction
            self._on_state_changed()
        return call_result.StartTransaction(
            transaction_id=transaction.transaction_id, id_tag_info=id_tag_info
        )

    @on(Action.stop_transaction)
    def on_stop_transaction(
        self, meter_stop: int, timestamp: str, transaction_id: int, **kwargs: Any
    ) -> call_result.StopTransaction:
        """Close the session; stopping is always accepted."""
        open_transaction = self.state.transaction
        if open_transaction is not None:
            self.state.last_transaction_energy_wh = max(
                meter_stop - open_transaction.meter_start_wh, 0.0
            )
        self.state.transaction = None
        self._on_state_changed()
        return call_result.StopTransaction(
            id_tag_info=IdTagInfo(status=AuthorizationStatus.accepted)
        )

    @on(Action.firmware_status_notification)
    def on_firmware_status(
        self, status: str, **kwargs: Any
    ) -> call_result.FirmwareStatusNotification:
        """Log firmware updates the charger performs on its own."""
        _LOGGER.info("%s: firmware status %s", self.id, status)
        return call_result.FirmwareStatusNotification()

    @on(Action.diagnostics_status_notification)
    def on_diagnostics_status(
        self, status: str, **kwargs: Any
    ) -> call_result.DiagnosticsStatusNotification:
        """Log diagnostics uploads."""
        _LOGGER.info("%s: diagnostics status %s", self.id, status)
        return call_result.DiagnosticsStatusNotification()

    def _authorize(self, id_tag: IdTag) -> IdTagInfo:
        allowed = self._authorizer.is_allowed(self.state.serial, id_tag)
        self.state.last_authorization = AuthorizationAttempt(
            id_tag=id_tag, accepted=allowed, timestamp=dt_util.utcnow()
        )
        if allowed:
            _LOGGER.info("%s: RFID authorization accepted", self.id)
        else:
            _LOGGER.warning(
                "%s: RFID authorization rejected (not on the whitelist)", self.id
            )
        self._on_state_changed()
        status = (
            AuthorizationStatus.accepted if allowed else AuthorizationStatus.invalid
        )
        return IdTagInfo(status=status)

    async def request(self, payload: Any) -> Any:
        """Send a call and return its result; raise CommandFailedError on CALLERROR, timeout or a closed connection."""
        try:
            return await self.call(payload, suppress=False)
        except (OCPPError, TimeoutError, ConnectionError) as error:
            raise CommandFailedError(f"{type(payload).__name__}: {error}") from error

    async def request_accepted(self, payload: Any) -> None:
        """Send a call whose result carries a status that must be Accepted."""
        result = await self.request(payload)
        if not is_accepted(result.status):
            raise CommandFailedError(f"{type(payload).__name__}: {result.status}")

    async def read_configuration(
        self, keys: list[str] | None = None
    ) -> dict[str, ConfigurationValue]:
        """Read configuration keys (all visible keys if none given) into the state."""
        result = await self.request(call.GetConfiguration(key=keys))
        read_values = {
            entry["key"]: ConfigurationValue(
                value=entry.get("value"), readonly=bool(entry["readonly"])
            )
            for entry in result.configuration_key or []
        }
        self.state.configuration.update(read_values)
        self.state.unsupported_configuration_keys.update(result.unknown_key or [])
        self._on_state_changed()
        return read_values

    async def change_configuration(self, key: str, value: str) -> str:
        """Change a configuration key; returns Accepted or RebootRequired, raises otherwise."""
        result = await self.request(call.ChangeConfiguration(key=key, value=value))
        status = str(result.status)
        if status not in {ACCEPTED, "RebootRequired"}:
            raise CommandFailedError(f"ChangeConfiguration {key}={value}: {status}")
        previous = self.state.configuration.get(key)
        readonly = previous.readonly if previous is not None else False
        self.state.configuration[key] = ConfigurationValue(
            value=value, readonly=readonly
        )
        self._on_state_changed()
        return status

    async def trigger_message(
        self, message: MessageTrigger, connector_id: int | None = None
    ) -> None:
        """Ask the charger to send a message now."""
        await self.request_accepted(
            call.TriggerMessage(requested_message=message, connector_id=connector_id)
        )

    async def set_charge_point_max_current(self, amps: float) -> None:
        """Limit the whole charger (stays in force until replaced)."""
        await self._set_profile(MAX_CURRENT_SLOT, amps)

    async def set_control_limit(self, amps: float, valid_for: timedelta) -> None:
        """Limit the charger for valid_for; afterwards the max current applies again."""
        await self._set_profile(CONTROL_LIMIT_SLOT, amps, valid_for)

    async def set_tx_default_current(self, amps: float) -> None:
        """Default limit for every new charging session."""
        await self._set_profile(TX_DEFAULT_SLOT, amps)

    async def _set_profile(
        self, slot: ProfileSlot, amps: float, valid_for: timedelta | None = None
    ) -> None:
        schedule_start = dt_util.utcnow() - SCHEDULE_START_LEAD
        # The schedule starts SCHEDULE_START_LEAD in the past, so the duration includes it.
        duration = (
            int((valid_for + SCHEDULE_START_LEAD).total_seconds())
            if valid_for
            else None
        )
        profile = ChargingProfile(
            charging_profile_id=slot.profile_id,
            stack_level=slot.stack_level,
            charging_profile_purpose=slot.purpose,
            charging_profile_kind=ChargingProfileKindType.absolute,
            charging_schedule=ChargingSchedule(
                charging_rate_unit=ChargingRateUnitType.amps,
                charging_schedule_period=[
                    ChargingSchedulePeriod(start_period=0, limit=amps)
                ],
                start_schedule=ocpp_timestamp(schedule_start),
                duration=duration,
            ),
        )
        await self.request_accepted(
            call.SetChargingProfile(
                connector_id=slot.connector_id, cs_charging_profiles=profile
            )
        )

    async def clear_charging_profiles(self, **criteria: Any) -> None:
        """Remove charging profiles (all of them without criteria)."""
        await self.request_accepted(call.ClearChargingProfile(**criteria))

    async def read_composite_limit(
        self, duration: timedelta = timedelta(minutes=1)
    ) -> float | None:
        """Return the limit currently in force for the vehicle connector."""
        result = await self.request(
            call.GetCompositeSchedule(
                connector_id=CONNECTOR_ID_VEHICLE,
                duration=int(duration.total_seconds()),
                charging_rate_unit=ChargingRateUnitType.amps,
            )
        )
        periods = (result.charging_schedule or {}).get("charging_schedule_period", [])
        limit = float(periods[0]["limit"]) if periods else None
        self.state.composite_limit_amps = limit
        self._on_state_changed()
        return limit

    async def set_charging_profile(
        self, connector_id: int, profile: dict[str, Any]
    ) -> None:
        """Install an arbitrary charging profile (camelCase or snake_case keys)."""
        await self.request_accepted(
            call.SetChargingProfile(
                connector_id=connector_id, cs_charging_profiles=profile
            )
        )

    async def composite_schedule(
        self, connector_id: int, duration: timedelta
    ) -> dict[str, Any]:
        """Return the raw composite schedule of a connector."""
        result = await self.request(
            call.GetCompositeSchedule(
                connector_id=connector_id,
                duration=int(duration.total_seconds()),
                charging_rate_unit=ChargingRateUnitType.amps,
            )
        )
        return {
            "status": str(result.status),
            "schedule_start": result.schedule_start,
            "charging_schedule": without_decimals(result.charging_schedule),
        }

    async def send_local_list(
        self, version: int, full_update: bool, id_tags: list[IdTag]
    ) -> None:
        """Replace (full) or extend (differential) the charger's local authorization list."""
        entries = [
            {"id_tag": tag, "id_tag_info": {"status": AuthorizationStatus.accepted}}
            for tag in id_tags
        ]
        await self.request_accepted(
            call.SendLocalList(
                list_version=version,
                update_type=UpdateType.full if full_update else UpdateType.differential,
                local_authorization_list=entries,
            )
        )

    async def local_list_version(self) -> int:
        """Version of the local authorization list on the charger."""
        result = await self.request(call.GetLocalListVersion())
        return int(result.list_version)

    async def change_availability(self, operative: bool) -> None:
        """Enable or disable the charger."""
        availability = (
            AvailabilityType.operative if operative else AvailabilityType.inoperative
        )
        result = await self.request(
            call.ChangeAvailability(
                connector_id=CONNECTOR_ID_CHARGE_POINT, type=availability
            )
        )
        if str(result.status) not in {ACCEPTED, "Scheduled"}:
            raise CommandFailedError(f"ChangeAvailability: {result.status}")

    async def reset(self, hard: bool) -> None:
        """Restart the charger."""
        await self.request_accepted(
            call.Reset(type=ResetType.hard if hard else ResetType.soft)
        )

    async def unlock_connector(self) -> None:
        """Release the cable."""
        result = await self.request(
            call.UnlockConnector(connector_id=CONNECTOR_ID_VEHICLE)
        )
        if str(result.status) != "Unlocked":
            raise CommandFailedError(f"UnlockConnector: {result.status}")

    async def remote_start(self, id_tag: IdTag) -> None:
        """Start charging as if the card had been presented."""
        await self.request_accepted(
            call.RemoteStartTransaction(
                id_tag=id_tag, connector_id=CONNECTOR_ID_VEHICLE
            )
        )

    async def remote_stop(self) -> None:
        """Stop the open session."""
        transaction = self.state.transaction
        if transaction is None:
            raise CommandFailedError("RemoteStopTransaction: no open transaction")
        await self.request_accepted(
            call.RemoteStopTransaction(transaction_id=transaction.transaction_id)
        )
