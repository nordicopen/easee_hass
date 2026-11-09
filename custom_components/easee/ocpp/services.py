"""Actions that expose the OCPP commands the entities do not cover."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from contextlib import suppress
from datetime import timedelta
from typing import Any

import probatio

from homeassistant.core import (
    HomeAssistant,
    ServiceCall,
    ServiceResponse,
    SupportsResponse,
)
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError
from homeassistant.helpers import config_validation as cv, device_registry as dr
from homeassistant.util.json import JsonValueType

from ..const import DOMAIN
from .charge_point import CommandFailedError, EaseeChargePoint
from .const import CONNECTOR_ID_CHARGE_POINT, CONNECTOR_ID_VEHICLE
from .hub import OcppHub
from .models import Serial
from .server import HUB_DATA_KEY

ATTR_DEVICE_ID = "device_id"
ATTR_KEY = "key"
ATTR_VALUE = "value"
ATTR_CONNECTOR_ID = "connector_id"
ATTR_CHARGING_PROFILE = "charging_profile"
ATTR_PROFILE_ID = "profile_id"
ATTR_PURPOSE = "purpose"
ATTR_STACK_LEVEL = "stack_level"
ATTR_DURATION = "duration"
ATTR_MESSAGE = "message"
ATTR_ID_TAGS = "id_tags"
ATTR_VERSION = "version"
ATTR_FULL_UPDATE = "full_update"

TRIGGERABLE_MESSAGES = [
    "BootNotification",
    "DiagnosticsStatusNotification",
    "FirmwareStatusNotification",
    "Heartbeat",
    "MeterValues",
    "StatusNotification",
]
PROFILE_PURPOSES = ["ChargePointMaxProfile", "TxDefaultProfile", "TxProfile"]
DEFAULT_SCHEDULE_DURATION_SECONDS = 3600

type ServiceHandler = Callable[
    [EaseeChargePoint, ServiceCall], Awaitable[ServiceResponse]
]

ATTR_SERIAL = "serial"
ATTR_CURRENT = "current"
TARGET_SCHEMA = {
    probatio.Optional(ATTR_DEVICE_ID): cv.string,
    probatio.Optional(ATTR_SERIAL): cv.string,
}
MAX_CURRENT_AMPS = 32
DEFAULT_CONTROL_LIMIT_SECONDS = 120
CONNECTOR = probatio.All(
    probatio.Coerce(int),
    probatio.Range(min=CONNECTOR_ID_CHARGE_POINT, max=CONNECTOR_ID_VEHICLE),
)


async def set_current_limit(
    charge_point: EaseeChargePoint, call: ServiceCall
) -> ServiceResponse:
    """Set a limit that expires after duration unless renewed (for external controllers)."""
    await charge_point.set_control_limit(
        call.data[ATTR_CURRENT], timedelta(seconds=call.data[ATTR_DURATION])
    )
    # Only refreshes the limit sensor; the limit itself is already set.
    with suppress(CommandFailedError):
        await charge_point.read_composite_limit()
    return None


async def get_configuration(
    charge_point: EaseeChargePoint, call: ServiceCall
) -> ServiceResponse:
    """GetConfiguration: all visible keys, or one key (also hidden Easee keys)."""
    key: str | None = call.data.get(ATTR_KEY)
    values = await charge_point.read_configuration([key] if key else None)
    unknown_keys: list[JsonValueType] = []
    unknown_keys.extend(sorted(charge_point.state.unsupported_configuration_keys))
    return {
        "configuration": {
            name: {"value": entry.value, "readonly": entry.readonly}
            for name, entry in values.items()
        },
        "unknown_keys": unknown_keys,
    }


async def change_configuration(
    charge_point: EaseeChargePoint, call: ServiceCall
) -> ServiceResponse:
    """ChangeConfiguration of one key."""
    status = await charge_point.change_configuration(
        call.data[ATTR_KEY], str(call.data[ATTR_VALUE])
    )
    return {"status": status}


async def set_charging_profile(
    charge_point: EaseeChargePoint, call: ServiceCall
) -> ServiceResponse:
    """SetChargingProfile with a profile written by the user."""
    await charge_point.set_charging_profile(
        call.data[ATTR_CONNECTOR_ID], call.data[ATTR_CHARGING_PROFILE]
    )
    return None


async def clear_charging_profile(
    charge_point: EaseeChargePoint, call: ServiceCall
) -> ServiceResponse:
    """ClearChargingProfile; without criteria all profiles are removed."""
    criteria_by_attribute = {
        ATTR_PROFILE_ID: "id",
        ATTR_CONNECTOR_ID: "connector_id",
        ATTR_PURPOSE: "charging_profile_purpose",
        ATTR_STACK_LEVEL: "stack_level",
    }
    criteria = {
        ocpp_name: call.data[attribute]
        for attribute, ocpp_name in criteria_by_attribute.items()
        if attribute in call.data
    }
    await charge_point.clear_charging_profiles(**criteria)
    return None


async def get_composite_schedule(
    charge_point: EaseeChargePoint, call: ServiceCall
) -> ServiceResponse:
    """GetCompositeSchedule: the limits in force over the next seconds."""
    duration = timedelta(seconds=call.data[ATTR_DURATION])
    return await charge_point.composite_schedule(call.data[ATTR_CONNECTOR_ID], duration)


async def trigger_message(
    charge_point: EaseeChargePoint, call: ServiceCall
) -> ServiceResponse:
    """TriggerMessage."""
    await charge_point.trigger_message(
        call.data[ATTR_MESSAGE], call.data.get(ATTR_CONNECTOR_ID)
    )
    return None


async def send_local_list(
    charge_point: EaseeChargePoint, call: ServiceCall
) -> ServiceResponse:
    """SendLocalList: cards the charger accepts on its own while offline (max. 10 on Easee)."""
    await charge_point.send_local_list(
        call.data[ATTR_VERSION], call.data[ATTR_FULL_UPDATE], call.data[ATTR_ID_TAGS]
    )
    return None


async def get_local_list_version(
    charge_point: EaseeChargePoint, call: ServiceCall
) -> ServiceResponse:
    """GetLocalListVersion."""
    return {"version": await charge_point.local_list_version()}


SERVICES: dict[str, tuple[ServiceHandler, dict[Any, Any], SupportsResponse]] = {
    "ocpp_set_current_limit": (
        set_current_limit,
        {
            probatio.Required(ATTR_CURRENT): probatio.All(
                probatio.Coerce(float), probatio.Range(min=0, max=MAX_CURRENT_AMPS)
            ),
            probatio.Optional(
                ATTR_DURATION, default=DEFAULT_CONTROL_LIMIT_SECONDS
            ): probatio.All(probatio.Coerce(int), probatio.Range(min=10, max=86400)),
        },
        SupportsResponse.NONE,
    ),
    "ocpp_get_configuration": (
        get_configuration,
        {probatio.Optional(ATTR_KEY): cv.string},
        SupportsResponse.ONLY,
    ),
    "ocpp_change_configuration": (
        change_configuration,
        {
            probatio.Required(ATTR_KEY): cv.string,
            probatio.Required(ATTR_VALUE): cv.string,
        },
        SupportsResponse.OPTIONAL,
    ),
    "ocpp_set_charging_profile": (
        set_charging_profile,
        {
            probatio.Optional(
                ATTR_CONNECTOR_ID, default=CONNECTOR_ID_CHARGE_POINT
            ): CONNECTOR,
            probatio.Required(ATTR_CHARGING_PROFILE): dict,
        },
        SupportsResponse.NONE,
    ),
    "ocpp_clear_charging_profile": (
        clear_charging_profile,
        {
            probatio.Optional(ATTR_PROFILE_ID): probatio.Coerce(int),
            probatio.Optional(ATTR_CONNECTOR_ID): CONNECTOR,
            probatio.Optional(ATTR_PURPOSE): probatio.In(PROFILE_PURPOSES),
            probatio.Optional(ATTR_STACK_LEVEL): probatio.Coerce(int),
        },
        SupportsResponse.NONE,
    ),
    "ocpp_get_composite_schedule": (
        get_composite_schedule,
        {
            probatio.Optional(
                ATTR_CONNECTOR_ID, default=CONNECTOR_ID_VEHICLE
            ): CONNECTOR,
            probatio.Optional(
                ATTR_DURATION, default=DEFAULT_SCHEDULE_DURATION_SECONDS
            ): probatio.Coerce(int),
        },
        SupportsResponse.ONLY,
    ),
    "ocpp_trigger_message": (
        trigger_message,
        {
            probatio.Required(ATTR_MESSAGE): probatio.In(TRIGGERABLE_MESSAGES),
            probatio.Optional(ATTR_CONNECTOR_ID): CONNECTOR,
        },
        SupportsResponse.NONE,
    ),
    "ocpp_send_local_list": (
        send_local_list,
        {
            probatio.Required(ATTR_ID_TAGS): [cv.string],
            probatio.Required(ATTR_VERSION): probatio.Coerce(int),
            probatio.Optional(ATTR_FULL_UPDATE, default=True): cv.boolean,
        },
        SupportsResponse.NONE,
    ),
    "ocpp_get_local_list_version": (get_local_list_version, {}, SupportsResponse.ONLY),
}


def target_serial(hass: HomeAssistant, call: ServiceCall) -> Serial:
    """Return the serial the action targets, given as serial or as device."""
    if ATTR_SERIAL in call.data:
        serial: Serial = call.data[ATTR_SERIAL]
        return serial
    return serial_of_device(hass, call.data[ATTR_DEVICE_ID])


def serial_of_device(hass: HomeAssistant, device_id: str) -> Serial:
    """Return the charger serial behind a device id."""
    device = dr.async_get(hass).async_get(device_id)
    serials = (
        [identifier for domain, identifier in device.identifiers if domain == DOMAIN]
        if device
        else []
    )
    if not serials:
        raise ServiceValidationError(f"{device_id} is not an Easee charger")
    return serials[0]


def charge_point_for(hass: HomeAssistant, call: ServiceCall) -> EaseeChargePoint:
    """Return the connected charge point the action targets."""
    hub: OcppHub | None = hass.data.get(HUB_DATA_KEY)
    serial = target_serial(hass, call)
    if hub is None or not hub.knows(serial):
        raise ServiceValidationError(f"{serial} is not connected via local OCPP")
    try:
        return hub.charge_point(serial)
    except CommandFailedError as error:
        raise HomeAssistantError(str(error)) from error


def async_setup_ocpp_services(hass: HomeAssistant) -> None:
    """Register all OCPP actions."""
    for name, (handler, fields, supports_response) in SERVICES.items():

        async def handle(
            call: ServiceCall, handler: ServiceHandler = handler
        ) -> ServiceResponse:
            try:
                return await handler(charge_point_for(hass, call), call)
            except CommandFailedError as error:
                raise HomeAssistantError(str(error)) from error

        hass.services.async_register(
            DOMAIN,
            name,
            handle,
            schema=probatio.All(
                probatio.Schema({**TARGET_SCHEMA, **fields}),
                cv.has_at_least_one_key(ATTR_DEVICE_ID, ATTR_SERIAL),
            ),
            supports_response=supports_response,
        )
