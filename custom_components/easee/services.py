"""Easee services."""

from datetime import timedelta
import logging

import probatio
from pyeasee.exceptions import BadRequestException, ForbiddenServiceException

from homeassistant.const import CONF_DEVICE_ID
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError
from homeassistant.helpers import (
    config_validation as cv,
    device_registry as dr,
)
from homeassistant.util import dt as dt_util

from .const import DOMAIN
from .controller import Charger, Controller, Equalizer

# pylint: disable=broad-except

_LOGGER = logging.getLogger(__name__)

ACCESS_LEVEL = "access_level"
ACCESS_LEVELS = {"open_for_all": 1, "require_easee_account": 2, "whitelist": 3}
WEEKDAYS = {
    "monday": 0,
    "tuesday": 1,
    "wednesday": 2,
    "thursday": 3,
    "friday": 4,
    "saturday": 5,
    "sunday": 6,
}
CHARGER_ID = "charger_id"
CIRCUIT_ID = "circuit_id"
EQUALIZER_ID = "equalizer_id"
ATTR_CHARGEPLAN_START_DATETIME = "start_datetime"
ATTR_CHARGEPLAN_STOP_DATETIME = "stop_datetime"
ATTR_CHARGEPLAN_REPEAT = "repeat"
ATTR_CHARGEPLAN_DAY = "day"
ATTR_CHARGEPLAN_START_TIME = "start_time"
ATTR_CHARGEPLAN_STOP_TIME = "stop_time"
ATTR_SET_CURRENT = "current"
ATTR_SET_CURRENTP1 = "current_p1"
ATTR_SET_CURRENTP2 = "current_p2"
ATTR_SET_CURRENTP3 = "current_p3"
ATTR_COST_PER_KWH = "cost_per_kwh"
ATTR_COST_CURRENCY = "currency_id"
ATTR_COST_VAT = "vat"
ATTR_ENABLE = "enable"
ATTR_TTL = "time_to_live"
ATTR_PHASE_MODE = "phase_mode"
ATTR_1PHASE = "1_phase"
ATTR_AUTOPHASE = "auto_phase"
ATTR_3PHASE = "3_phase"
ATTR_PHASE_MODES = {
    ATTR_1PHASE: 1,
    ATTR_AUTOPHASE: 2,
    ATTR_3PHASE: 3,
}
ATTR_OCPP_URL = "ocpp_url"
ATTR_OPERATOR = "operator_id"
ACTION_COMMAND = "action_command"
ACTION_START = "start"
ACTION_STOP = "stop"
ACTION_PAUSE = "pause"
ACTION_RESUME = "resume"
ACTION_TOGGLE = "toggle"
ACTION_REBOOT = "reboot"
ACTION_UPDATE_FIRMWARE = "update_firmware"
ACTION_OVERRIDE_SCHEDULE = "override_schedule"
ACTION_DELETE_BASIC_CHARGE_PLAN = "delete_basic_charge_plan"
ACTION_ENABLE_BASIC_CHARGE_PLAN = "enable_basic_charge_plan"
ACTION_DISABLE_BASIC_CHARGE_PLAN = "disable_basic_charge_plan"
ACTION_DELETE_WEEKLY_CHARGE_PLAN = "delete_weekly_charge_plan"
ACTION_ENABLE_WEEKLY_CHARGE_PLAN = "enable_weekly_charge_plan"
ACTION_DISABLE_WEEKLY_CHARGE_PLAN = "disable_weekly_charge_plan"
ACTIONS = {
    ACTION_START,
    ACTION_STOP,
    ACTION_PAUSE,
    ACTION_RESUME,
    ACTION_TOGGLE,
    ACTION_REBOOT,
    ACTION_UPDATE_FIRMWARE,
    ACTION_OVERRIDE_SCHEDULE,
    ACTION_DELETE_BASIC_CHARGE_PLAN,
    ACTION_ENABLE_BASIC_CHARGE_PLAN,
    ACTION_DISABLE_BASIC_CHARGE_PLAN,
    ACTION_DELETE_WEEKLY_CHARGE_PLAN,
    ACTION_ENABLE_WEEKLY_CHARGE_PLAN,
    ACTION_DISABLE_WEEKLY_CHARGE_PLAN,
}

MIN_CURRENT = 0
MAX_CURRENT = 40
DEFAULT_CURRENT = 16

GRP1 = "group_1"

wd_name = [
    "monday",
    "tuesday",
    "wednesday",
    "thursday",
    "friday",
    "saturday",
    "sunday",
]


def has_at_least_one(keys):
    """Ensure that at least one key is present."""

    def fkey(obj):
        for k in obj:
            if k in keys:
                return obj
        raise probatio.Invalid(f"Must contain one of {keys}")

    return fkey


target_schema2 = has_at_least_one([CONF_DEVICE_ID, CHARGER_ID])
target_eq_schema2 = has_at_least_one([CONF_DEVICE_ID, EQUALIZER_ID])
target_schema3 = has_at_least_one([CONF_DEVICE_ID, CHARGER_ID, CIRCUIT_ID])

exclusive_schema2 = probatio.Schema(
    {
        probatio.Exclusive(CONF_DEVICE_ID, GRP1): cv.string,
        probatio.Exclusive(CHARGER_ID, GRP1): cv.string,
    },
    required=True,
)

exclusive_eq_schema2 = probatio.Schema(
    {
        probatio.Exclusive(CONF_DEVICE_ID, GRP1): cv.string,
        probatio.Exclusive(EQUALIZER_ID, GRP1): cv.string,
    },
    required=True,
)

exclusive_schema3 = probatio.Schema(
    {
        probatio.Exclusive(CONF_DEVICE_ID, GRP1): cv.string,
        probatio.Exclusive(CHARGER_ID, GRP1): cv.string,
        probatio.Exclusive(CIRCUIT_ID, GRP1): cv.positive_int,
    },
    required=True,
)

ext_charger_actions_command = {
    probatio.Required(ACTION_COMMAND): probatio.In(ACTIONS),
}
SERVICE_CHARGER_ACTIONS_COMMAND_SCHEMA = probatio.All(
    target_schema2,
    exclusive_schema2.extend(ext_charger_actions_command),
)

ext_charger_enable = {
    probatio.Required(ATTR_ENABLE): cv.boolean,
}

SERVICE_CHARGER_ENABLE_SCHEMA = probatio.All(
    target_schema2,
    exclusive_schema2.extend(ext_charger_enable),
)

ext_basic_chargeplan = {
    probatio.Optional(ATTR_CHARGEPLAN_START_DATETIME): cv.datetime,
    probatio.Optional(ATTR_CHARGEPLAN_STOP_DATETIME): cv.datetime,
    probatio.Optional(ATTR_CHARGEPLAN_REPEAT): cv.boolean,
    probatio.Optional(ATTR_SET_CURRENT): cv.positive_int,
}

SERVICE_CHARGER_SET_BASIC_CHARGEPLAN_SCHEMA = probatio.All(
    target_schema2,
    exclusive_schema2.extend(ext_basic_chargeplan),
)

ext_weekly_chargeplan = {
    probatio.Required(ATTR_CHARGEPLAN_DAY, default="monday"): probatio.In(WEEKDAYS),
    probatio.Optional(ATTR_CHARGEPLAN_START_TIME): cv.time,
    probatio.Optional(ATTR_CHARGEPLAN_STOP_TIME): cv.time,
    probatio.Optional(ATTR_SET_CURRENT): cv.positive_int,
}

SERVICE_CHARGER_SET_WEEKLY_CHARGEPLAN_SCHEMA = probatio.All(
    target_schema2,
    exclusive_schema2.extend(ext_weekly_chargeplan),
)

ext_circuit_current = {
    probatio.Optional(ATTR_SET_CURRENTP1, default=DEFAULT_CURRENT): cv.positive_int,
    probatio.Optional(ATTR_SET_CURRENTP2): cv.positive_int,
    probatio.Optional(ATTR_SET_CURRENTP3): cv.positive_int,
}

SERVICE_SET_CIRCUIT_CURRENT_SCHEMA = probatio.All(
    target_schema3,
    exclusive_schema3.extend(ext_circuit_current),
)

ext_ttl = {
    probatio.Optional(ATTR_TTL, default=0): cv.positive_int,
}

SERVICE_SET_CIRCUIT_CURRENT_SCHEMA_TTL = probatio.All(
    target_schema3,
    exclusive_schema3.extend(ext_circuit_current).extend(ext_ttl),
)

ext_current = {
    probatio.Required(ATTR_SET_CURRENT, default=DEFAULT_CURRENT): probatio.All(
        cv.positive_int, probatio.Range(min=MIN_CURRENT, max=MAX_CURRENT)
    ),
}

SERVICE_SET_CHARGER_CURRENT_SCHEMA = probatio.All(
    target_schema2,
    exclusive_schema2.extend(ext_current),
)

SERVICE_SET_CHARGER_CURRENT_SCHEMA_TTL = probatio.All(
    target_schema2,
    exclusive_schema2.extend(ext_current).extend(ext_ttl),
)

ext_cost = {
    probatio.Required(ATTR_COST_PER_KWH): probatio.All(probatio.Coerce(float)),
    probatio.Optional(ATTR_COST_CURRENCY): cv.string,
    probatio.Optional(ATTR_COST_VAT): probatio.All(probatio.Coerce(float)),
}

SERVICE_SET_SITE_CHARGING_COST_SCHEMA = probatio.All(
    target_schema2,
    exclusive_schema2.extend(ext_cost),
)

ext_access = {
    probatio.Required(ACCESS_LEVEL): probatio.In(ACCESS_LEVELS),
}
SERVICE_SET_ACCESS_SCHEMA = probatio.All(
    target_schema2,
    exclusive_schema2.extend(ext_access),
)

ext_phase_mode = {
    probatio.Required(ATTR_PHASE_MODE): probatio.In(ATTR_PHASE_MODES),
}
SERVICE_SET_PHASE_MODE = probatio.All(
    target_schema2,
    exclusive_schema2.extend(ext_phase_mode),
)

ext_surplus_charging = {
    probatio.Required(ATTR_ENABLE): cv.boolean,
    probatio.Required(ATTR_SET_CURRENT, default=MIN_CURRENT): probatio.All(
        cv.positive_int, probatio.Range(min=MIN_CURRENT, max=MAX_CURRENT)
    ),
}

ext_max_continuous_current = {
    probatio.Required(ATTR_SET_CURRENT, default=MIN_CURRENT): probatio.All(
        cv.positive_int, probatio.Range(min=MIN_CURRENT, max=MAX_CURRENT)
    ),
}

SERVICE_SET_SURPLUS_CHARGING_SCHEMA = probatio.All(
    target_eq_schema2,
    exclusive_eq_schema2.extend(ext_surplus_charging),
)

SERVICE_SET_MAX_CONTINUOUS_CURRENT_SCHEMA = probatio.All(
    target_eq_schema2,
    exclusive_eq_schema2.extend(ext_max_continuous_current),
)

ext_ocpp_mode = {
    probatio.Required(ATTR_ENABLE): cv.boolean,
    probatio.Optional(ATTR_OCPP_URL): cv.string,
}

ext_operator = {
    probatio.Required(ATTR_OPERATOR): cv.positive_int,
}

SERVICE_SET_OCPP = probatio.All(
    target_schema2,
    exclusive_schema2.extend(ext_ocpp_mode),
)

SERVICE_SET_OPERATOR = probatio.All(
    target_schema2,
    exclusive_schema2.extend(ext_operator),
)


async def async_convert_device_id_to_product_id(call: ServiceCall) -> str | None:
    """Convert device_id to product_id."""
    product_id = None
    device_reg = dr.async_get(call.hass)
    device_entry = device_reg.async_get(call.data[CONF_DEVICE_ID])
    if device_entry is None:
        raise ServiceValidationError(
            f"Could not find device_id {call.data[CONF_DEVICE_ID]}"
        )
    for ident in device_entry.identifiers:
        for val in ident:
            if val != DOMAIN:
                product_id = val
    return product_id


async def _async_get_charger(call: ServiceCall) -> Charger:
    controller: Controller = call.hass.data[DOMAIN]["controller"]
    chargers = controller.get_chargers()
    if CONF_DEVICE_ID in call.data:
        charger_id = await async_convert_device_id_to_product_id(call)
    else:
        charger_id = call.data[CHARGER_ID]
    charger = next((c for c in chargers if c.id == charger_id), None)
    if charger is None:
        raise ServiceValidationError(f"Could not find charger_id {charger_id}")
    return charger


async def _async_get_circuit_id(call: ServiceCall) -> int:
    if CIRCUIT_ID in call.data:
        return int(call.data[CIRCUIT_ID])
    charger = await _async_get_charger(call)
    return charger.circuit.id


async def _async_get_equalizer(call: ServiceCall) -> Equalizer:
    controller: Controller = call.hass.data[DOMAIN]["controller"]
    if CONF_DEVICE_ID in call.data:
        equalizer_id = await async_convert_device_id_to_product_id(call)
    else:
        equalizer_id = call.data[EQUALIZER_ID]
    equalizers = controller.get_equalizers()
    equalizer = next((e for e in equalizers if e.id == equalizer_id), None)
    if equalizer is None:
        raise ServiceValidationError(f"Could not find equalizer_id {equalizer_id}")
    return equalizer


async def charger_execute_service(call: ServiceCall) -> None:
    """Execute a service to Easee charging station."""

    charger = await _async_get_charger(call)
    enable = call.data.get(ATTR_ENABLE)

    _LOGGER.debug("execute_service: %s %s", str(call.service), str(call.data))

    if charger:
        function_name = SERVICE_MAP[call.service]
        function_call = getattr(charger, function_name["function_call"])
        try:
            if enable is not None:
                return await function_call(enable)
            else:
                return await function_call()
        except BadRequestException as ex:
            _LOGGER.error(
                "Bad request: [%s] - Invalid parameters or command not allowed now: %s",
                str(call.service),
                ex,
            )
            return
        except ForbiddenServiceException as ex:
            _LOGGER.error(
                "Forbidden : [%s] - Check your access privileges: %s",
                str(call.service),
                ex,
            )
            return
        except Exception:
            _LOGGER.error(
                "Failed to execute service: %s with data %s",
                str(call.service),
                str(call.data),
            )
            return

    raise HomeAssistantError(
        f"Could not find charger: {call.data.get(CHARGER_ID, 'Unknown')}"
    )


async def charger_execute_action_command(call: ServiceCall) -> None:
    """Execute a service with an action command to Easee charging station."""

    enable = call.data.get(ATTR_ENABLE)
    charger = await _async_get_charger(call)

    _LOGGER.debug(
        "Call action service %s on charger_id: %s",
        call.data[ACTION_COMMAND],
        charger.id,
    )
    if charger:
        function_call = getattr(charger, call.data[ACTION_COMMAND])
        try:
            if enable is not None:
                return await function_call(enable)
            else:
                return await function_call()
        except BadRequestException as ex:
            # msg = ex.args[0].get("title", "")
            _LOGGER.error(
                "Bad request: [%s] - Invalid parameters or command not allowed now: %s",
                str(call.service),
                ex.message.get("title", ""),
            )
            return
        except ForbiddenServiceException:
            _LOGGER.error(
                "Forbidden service: %s - Check your access privileges",
                str(call.service),
            )
            return
        except Exception:
            _LOGGER.error(
                "Failed to execute service: %s with data %s",
                str(call.service),
                str(call.data),
            )
            return
    raise HomeAssistantError(f"Could not find charger: {charger.id}")


async def charger_execute_set_phase_mode(call: ServiceCall) -> None:
    """Execute a service with an action command to Easee charging station."""

    phase_mode = ATTR_PHASE_MODES[call.data[ATTR_PHASE_MODE]]
    charger = await _async_get_charger(call)

    _LOGGER.debug(
        "Call set phase mode %s on charger_id: %s",
        call.data[ATTR_PHASE_MODE],
        charger.id,
    )
    if charger:
        function_name = SERVICE_MAP[call.service]
        function_call = getattr(charger, function_name["function_call"])
        try:
            return await function_call(phase_mode)
        except BadRequestException as ex:
            # msg = ex.args[0].get("title", "")
            _LOGGER.error(
                "Bad request: [%s] - Invalid parameters or command not allowed now: %s",
                str(call.service),
                ex.message.get("title", ""),
            )
            return
        except ForbiddenServiceException:
            _LOGGER.error(
                "Forbidden service: %s - Check your access privileges",
                str(call.service),
            )
            return
        except Exception:
            _LOGGER.error(
                "Failed to execute service: %s with data %s",
                str(call.service),
                str(call.data),
            )
            return
    raise HomeAssistantError(f"Could not find charger: {charger.id}")


async def charger_set_schedule(call: ServiceCall) -> None:
    """Execute a set schedule call to Easee charging station."""
    charger = await _async_get_charger(call)
    # future versions of Easee API will allow multiple schedules, i.e. work-in-progress
    schedule_id = charger.id
    start_datetime = call.data.get(ATTR_CHARGEPLAN_START_DATETIME)
    stop_datetime = call.data.get(ATTR_CHARGEPLAN_STOP_DATETIME)
    repeat = call.data.get(ATTR_CHARGEPLAN_REPEAT)
    current = call.data.get(ATTR_SET_CURRENT)
    if current is None:
        current = 32
    _LOGGER.debug("execute_service: %s %s", str(call.service), str(call.data))

    if charger:
        function_name = SERVICE_MAP[call.service]
        function_call = getattr(charger, function_name["function_call"])
        stop_d = None if stop_datetime is None else dt_util.as_utc(stop_datetime)
        try:
            return await function_call(
                schedule_id,
                dt_util.as_utc(start_datetime),
                stop_d,
                repeat,
                limit=current,
            )
        except BadRequestException as ex:
            _LOGGER.error(
                "Bad request: [%s] - Invalid parameters or command not allowed now: %s",
                str(call.service),
                ex,
            )
            return
        except ForbiddenServiceException as ex:
            _LOGGER.error(
                "Forbidden : [%s] - Check your access privileges: %s",
                str(call.service),
                ex,
            )
            return
        except Exception as ex:  # pylint: disable=broad-except
            _LOGGER.error(
                "Failed to execute service: %s : %s with data %s",
                str(call.service),
                ex,
                str(call.data),
            )
            return

    raise HomeAssistantError("Could not find charger.")


async def charger_set_weekly_schedule(call: ServiceCall) -> None:
    """Execute a set schedule call to Easee charging station."""
    charger = await _async_get_charger(call)
    start_time = call.data.get(ATTR_CHARGEPLAN_START_TIME)
    stop_time = call.data.get(ATTR_CHARGEPLAN_STOP_TIME)
    current = call.data.get(ATTR_SET_CURRENT)
    if current is None:
        current = 32
    day: int = WEEKDAYS[call.data[ATTR_CHARGEPLAN_DAY]]

    _LOGGER.debug("execute_service: %s %s", str(call.service), str(call.data))

    if charger:
        function_name = SERVICE_MAP[call.service]
        function_call = getattr(charger, function_name["function_call"])
        now_dt = dt_util.now()
        now_wd = now_dt.weekday()
        now_td = timedelta(days=now_wd - day)
        now_dt = now_dt - now_td
        start_dt = dt_util.as_utc(
            now_dt.replace(
                hour=start_time.hour,
                minute=start_time.minute,
                second=0,
                microsecond=0,
            )
        )
        stop_dt = dt_util.as_utc(
            now_dt.replace(
                hour=stop_time.hour,
                minute=stop_time.minute,
                second=0,
                microsecond=0,
            )
        )
        if stop_dt < start_dt:
            stop_dt = stop_dt + timedelta(days=1)
        start_t = start_dt.strftime("%H:%M")
        stop_t = stop_dt.strftime("%H:%M")
        start_day = wd_name[start_dt.weekday()]
        stop_day = wd_name[stop_dt.weekday()]

        try:
            return await function_call(
                start_day, stop_day, start_t, stop_t, limit=current
            )
        except BadRequestException as ex:
            _LOGGER.error(
                "Bad request: [%s] - Invalid parameters or command not allowed now: %s",
                str(call.service),
                ex,
            )
            return
        except ForbiddenServiceException as ex:
            _LOGGER.error(
                "Forbidden : [%s] - Check your access privileges: %s",
                str(call.service),
                ex,
            )
            return
        except Exception as ex:  # pylint: disable=broad-except
            _LOGGER.error(
                "Failed to execute service: %s : %s with data %s",
                str(call.service),
                ex,
                str(call.data),
            )
            return

    raise HomeAssistantError("Could not find charger.")


async def circuit_execute_set_current(call: ServiceCall) -> None:
    """Execute a service to set currents for Easee circuit."""
    circuit_id = await _async_get_circuit_id(call)
    controller = call.hass.data[DOMAIN]["controller"]
    current_p1 = call.data.get(ATTR_SET_CURRENTP1)
    current_p2 = call.data.get(ATTR_SET_CURRENTP2)
    current_p3 = call.data.get(ATTR_SET_CURRENTP3)

    time_to_live = call.data.get(ATTR_TTL)

    _LOGGER.debug("Execute_service: %s %s", str(call.service), str(call.data))

    function_name = SERVICE_MAP[call.service]
    compare = function_name["compare_currents"]
    circuit = controller.check_circuit_current(
        circuit_id,
        current_p1,
        current_p2,
        current_p3,
        compare["P1"],
        compare["P2"],
        compare["P3"],
        time_to_live,
    )
    if circuit:
        function_call = getattr(circuit, function_name["function_call"])
        try:
            if time_to_live is not None:
                return await function_call(
                    current_p1, current_p2, current_p3, time_to_live
                )
            else:
                return await function_call(current_p1, current_p2, current_p3)
        except BadRequestException as ex:
            _LOGGER.error(
                "Bad request: [%s] - Invalid parameters or command not allowed now: %s",
                str(call.service),
                ex,
            )
            return
        except ForbiddenServiceException as ex:
            _LOGGER.error(
                "Forbidden : [%s] - Check your access privileges: %s",
                str(call.service),
                ex,
            )
            return
        except Exception:
            _LOGGER.error(
                "Failed to execute service: %s with data %s",
                str(call.service),
                str(call.data),
            )
            return

    if circuit is None:
        raise HomeAssistantError(f"Could not find circuit {circuit_id}")


async def charger_execute_set_current(call: ServiceCall) -> None:
    """Execute a service to set currents for Easee charger."""

    charger = await _async_get_charger(call)
    charger_id = charger.id
    controller = call.hass.data[DOMAIN]["controller"]
    _LOGGER.debug("Call set_current service on charger_id: %s", charger_id)

    current = call.data.get(ATTR_SET_CURRENT)
    time_to_live = call.data.get(ATTR_TTL)

    _LOGGER.debug("Execute_service: %s %s", str(call.service), str(call.data))

    function_name = SERVICE_MAP[call.service]
    compare = function_name["compare_currents"]
    charger = controller.check_charger_current(
        charger_id,
        current,
        current,
        current,
        compare["P1"],
        compare["P2"],
        compare["P3"],
        time_to_live,
    )
    if charger:
        function_call = getattr(charger, function_name["function_call"])
        try:
            if time_to_live is not None:
                return await function_call(current, time_to_live)
            else:
                return await function_call(current)
        except BadRequestException as ex:
            _LOGGER.error(
                "Bad request: [%s] - Invalid parameters or command not allowed now: %s",
                str(call.service),
                ex,
            )
            return
        except ForbiddenServiceException as ex:
            _LOGGER.error(
                "Forbidden : [%s] - Check your access privileges: %s",
                str(call.service),
                ex,
            )
            return
        except Exception:
            _LOGGER.error(
                "Failed to execute service: %s with data %s",
                str(call.service),
                str(call.data),
            )
            return

    if charger is None:
        raise HomeAssistantError(
            f"Could not find charger: {call.data.get(CHARGER_ID, 'Unknown')}"
        )


async def charger_execute_set_current_3(call: ServiceCall) -> None:
    """Execute a service to set currents for Easee charger."""

    charger = await _async_get_charger(call)
    charger_id = charger.id

    _LOGGER.debug("Call set_current service on charger_id: %s", charger_id)

    current_p1 = call.data.get(ATTR_SET_CURRENTP1)
    current_p2 = call.data.get(ATTR_SET_CURRENTP2)
    current_p3 = call.data.get(ATTR_SET_CURRENTP3)

    _LOGGER.debug("Execute_service: %s %s", str(call.service), str(call.data))

    function_name = SERVICE_MAP[call.service]
    compare = function_name["compare_currents"]
    controller = call.hass.data[DOMAIN]["controller"]
    charger = controller.check_charger_current(
        charger_id,
        current_p1,
        current_p2,
        current_p3,
        compare["P1"],
        compare["P2"],
        compare["P3"],
    )
    if charger:
        function_call = getattr(charger, function_name["function_call"])
        try:
            return await function_call(current_p1, current_p2, current_p3)
        except BadRequestException as ex:
            _LOGGER.error(
                "Bad request: [%s] - Invalid parameters or command not allowed now: %s",
                str(call.service),
                ex,
            )
            return
        except ForbiddenServiceException as ex:
            _LOGGER.error(
                "Forbidden : [%s] - Check your access privileges: %s",
                str(call.service),
                ex,
            )
            return
        except Exception:  # pylint: disable=broad-except
            _LOGGER.error(
                "Failed to execute service: %s with data %s",
                str(call.service),
                str(call.data),
            )
            return

    if charger is None:
        raise HomeAssistantError(
            f"Could not find charger: {call.data.get(CHARGER_ID, 'Unknown')}"
        )


async def charger_execute_set_charging_cost(call: ServiceCall) -> None:
    """Execute a service to set charging cost per kwh for Easee charger site."""
    charger = await _async_get_charger(call)
    cost_per_kwh = call.data.get(ATTR_COST_PER_KWH)
    currency = call.data.get(ATTR_COST_CURRENCY)
    vat = call.data.get(ATTR_COST_VAT)
    controller = call.hass.data[DOMAIN]["controller"]

    _LOGGER.debug("execute_service: %s %s", str(call.service), str(call.data))

    if charger:
        function_name = SERVICE_MAP[call.service]
        function_call = getattr(charger.site, function_name["function_call"])
        try:
            retval = await function_call(cost_per_kwh, vat, currency)
            await controller.async_force_site_notify(charger.site.id)
            return retval
        except BadRequestException as ex:
            _LOGGER.error(
                "Bad request: [%s] - Invalid parameters or command not allowed now: %s",
                str(call.service),
                ex,
            )
            return
        except ForbiddenServiceException as ex:
            _LOGGER.error(
                "Forbidden : [%s] - Check your access privileges: %s",
                str(call.service),
                ex,
            )
            return
        except Exception:
            _LOGGER.error(
                "Failed to execute service: %s with data %s",
                str(call.service),
                str(call.data),
            )
            return

    raise HomeAssistantError("Could not find charger")


async def equalizer_execute_set_surplus_charging(call: ServiceCall) -> None:
    """Execute a service to set load balancing for a site.

    Equalizer is the actual target for API.
    """
    equalizer = await _async_get_equalizer(call)
    enabled = call.data.get(ATTR_ENABLE)
    current = call.data.get(ATTR_SET_CURRENT)
    if current is None:
        current = 0

    _LOGGER.debug("execute_service: %s %s", str(call.service), str(call.data))

    if equalizer:
        function_name = SERVICE_MAP[call.service]
        function_call = getattr(equalizer, function_name["function_call"])
        try:
            return await function_call(enabled, current)
        except BadRequestException as ex:
            _LOGGER.error(
                "Bad request: [%s] - Invalid parameters or command not allowed now: %s",
                str(call.service),
                ex,
            )
            return
        except ForbiddenServiceException as ex:
            _LOGGER.error(
                "Forbidden : [%s] - Check your access privileges: %s",
                str(call.service),
                ex,
            )
            return
        except Exception:
            _LOGGER.error(
                "Failed to execute service: %s with data %s",
                str(call.service),
                str(call.data),
            )
            return

    raise HomeAssistantError("Could not find equalizer")


async def equalizer_execute_set_max_continuous_current(call):
    """Execute a service to set max continuous current for a site..

    Equalizer is the actual target for API.
    """
    equalizer = await _async_get_equalizer(call)
    current = call.data[ATTR_SET_CURRENT]

    _LOGGER.debug("execute_service: %s %s", str(call.service), str(call.data))

    if equalizer:
        function_name = SERVICE_MAP[call.service]
        function_call = getattr(equalizer, function_name["function_call"])
        try:
            return await function_call(current)
        except BadRequestException as ex:
            _LOGGER.error(
                "Bad request: [%s] - Invalid parameters or command not allowed now: %s",
                str(call.service),
                ex,
            )
            return
        except ForbiddenServiceException as ex:
            _LOGGER.error(
                "Forbidden : [%s] - Check your access privileges: %s",
                str(call.service),
                ex,
            )
            return
        except Exception as ex:
            _LOGGER.error(
                "Failed to execute service %s with data %s: %s",
                str(call.service),
                str(call.data),
                ex,
            )
            return

    raise HomeAssistantError("Could not find Equalizer")


async def charger_execute_set_access(call: ServiceCall) -> None:
    """Execute a service to set access level on a charger."""

    access_level = ACCESS_LEVELS[call.data[ACCESS_LEVEL]]

    charger = await _async_get_charger(call)

    if charger:
        function_name = SERVICE_MAP[call.service]
        function_call = getattr(charger, function_name["function_call"])
        try:
            return await function_call(access_level)
        except BadRequestException as ex:
            _LOGGER.error(
                "Bad request: [%s] - Invalid parameters or command not allowed now: %s",
                str(call.service),
                ex,
            )
            return
        except ForbiddenServiceException as ex:
            _LOGGER.error(
                "Forbidden : [%s] - Check your access privileges: %s",
                str(call.service),
                ex,
            )
            return
        except Exception:
            _LOGGER.error(
                "Failed to execute service: %s with data %s",
                str(call.service),
                str(call.data),
            )
            return
    raise HomeAssistantError(
        f"Could not find charger: {call.data.get(CHARGER_ID, 'Unknown')}"
    )


async def charger_execute_set_ocpp(call: ServiceCall) -> None:
    """Set the local OCPP configuration of a charger."""

    charger = await _async_get_charger(call)
    enable = call.data.get(ATTR_ENABLE)
    url = call.data.get(ATTR_OCPP_URL)

    if url is None:
        url = "ws://127.0.0.1:9000"

    _LOGGER.debug(
        "Call set ocpp enable %d on charger_id: %s with url %s", enable, charger.id, url
    )
    if charger:
        function_name = SERVICE_MAP[call.service]
        function_call = getattr(charger, function_name["function_call"])
        function_call_2 = getattr(charger, function_name["function_call_2"])
        try:
            version = await function_call(enable, url)
            return await function_call_2(version)
        except BadRequestException as ex:
            # msg = ex.args[0].get("title", "")
            _LOGGER.error(
                "Bad request: [%s] - Invalid parameters or command not allowed now: %s",
                str(call.service),
                ex.message.get("title", ""),
            )
            return
        except ForbiddenServiceException:
            _LOGGER.error(
                "Forbidden service: %s - Check your access privileges",
                str(call.service),
            )
            return
        except Exception:
            _LOGGER.error(
                "Failed to execute service: %s with data %s",
                str(call.service),
                str(call.data),
            )
            return
    raise HomeAssistantError(f"Could not find charger: {charger.id}")


async def charger_execute_set_operator(call: ServiceCall) -> None:
    """Set the operator of a charger."""

    controller = call.hass.data[DOMAIN]["controller"]
    charger = await _async_get_charger(call)
    operator_id = call.data.get(ATTR_OPERATOR)

    _LOGGER.debug(
        "Call set operator %d on charger_id: %s",
        operator_id,
        charger.id,
    )
    if charger:
        function_name = SERVICE_MAP[call.service]
        function_call = getattr(charger, function_name["function_call"])
        try:
            await function_call(operator_id)
            await controller.async_refresh_operator()
            return
        except BadRequestException:
            # In this case this probably means the operator is already set to the same value
            return
        except ForbiddenServiceException:
            _LOGGER.error(
                "Forbidden service: %s - Check your access privileges",
                str(call.service),
            )
            return
        except Exception as ex:
            _LOGGER.error(
                "Failed to execute service: %s with data %s %s",
                str(call.service),
                str(call.data),
                ex,
            )
            return
        # Update the operator sensor

    raise HomeAssistantError(f"Could not find charger: {charger.id}")


SERVICE_MAP = {
    "action_command": {
        "handler": charger_execute_action_command,
        "schema": SERVICE_CHARGER_ACTIONS_COMMAND_SCHEMA,
    },
    "smart_charging": {
        "handler": charger_execute_service,
        "function_call": "smart_charging",
        "schema": SERVICE_CHARGER_ENABLE_SCHEMA,
    },
    "set_basic_charge_plan": {
        "handler": charger_set_schedule,
        "function_call": "set_basic_charge_plan",
        "schema": SERVICE_CHARGER_SET_BASIC_CHARGEPLAN_SCHEMA,
    },
    "set_weekly_charge_plan": {
        "handler": charger_set_weekly_schedule,
        "function_call": "set_weekly_charge_plan",
        "schema": SERVICE_CHARGER_SET_WEEKLY_CHARGEPLAN_SCHEMA,
    },
    "set_circuit_dynamic_limit": {
        "handler": circuit_execute_set_current,
        "function_call": "set_dynamic_current",
        "compare_currents": {
            "P1": "dynamicCircuitCurrentP1",
            "P2": "dynamicCircuitCurrentP2",
            "P3": "dynamicCircuitCurrentP3",
        },
        "schema": SERVICE_SET_CIRCUIT_CURRENT_SCHEMA_TTL,
    },
    "set_circuit_max_limit": {
        "handler": circuit_execute_set_current,
        "function_call": "set_max_current",
        "compare_currents": {
            "P1": "circuitMaxCurrentP1",
            "P2": "circuitMaxCurrentP2",
            "P3": "circuitMaxCurrentP3",
        },
        "schema": SERVICE_SET_CIRCUIT_CURRENT_SCHEMA,
    },
    "set_circuit_offline_limit": {
        "handler": charger_execute_set_current_3,
        "function_call": "set_max_offline_charger_circuit_current",
        "compare_currents": {
            "P1": "offlineMaxCircuitCurrentP1",
            "P2": "offlineMaxCircuitCurrentP2",
            "P3": "offlineMaxCircuitCurrentP3",
        },
        "schema": SERVICE_SET_CIRCUIT_CURRENT_SCHEMA,
    },
    "set_charger_dynamic_limit": {
        "handler": charger_execute_set_current,
        "function_call": "set_dynamic_charger_current",
        "compare_currents": {
            "P1": "dynamicChargerCurrent",
            "P2": "dynamicChargerCurrent",
            "P3": "dynamicChargerCurrent",
        },
        "schema": SERVICE_SET_CHARGER_CURRENT_SCHEMA_TTL,
    },
    "set_charger_max_limit": {
        "handler": charger_execute_set_current,
        "function_call": "set_max_charger_current",
        "compare_currents": {
            "P1": "maxChargerCurrent",
            "P2": "maxChargerCurrent",
            "P3": "maxChargerCurrent",
        },
        "schema": SERVICE_SET_CHARGER_CURRENT_SCHEMA,
    },
    "set_charging_cost": {
        "handler": charger_execute_set_charging_cost,
        "function_call": "set_price",
        "schema": SERVICE_SET_SITE_CHARGING_COST_SCHEMA,
    },
    "set_charger_access": {
        "handler": charger_execute_set_access,
        "function_call": "set_access",
        "schema": SERVICE_SET_ACCESS_SCHEMA,
    },
    "set_charger_phase_mode": {
        "handler": charger_execute_set_phase_mode,
        "function_call": "phaseMode",
        "schema": SERVICE_SET_PHASE_MODE,
    },
    "set_surplus_charging": {
        "handler": equalizer_execute_set_surplus_charging,
        "function_call": "set_load_balancing",
        "schema": SERVICE_SET_SURPLUS_CHARGING_SCHEMA,
    },
    "set_equalizer_max_continuous_limit": {
        "handler": equalizer_execute_set_max_continuous_current,
        "function_call": "set_max_continuous_current",
        "schema": SERVICE_SET_MAX_CONTINUOUS_CURRENT_SCHEMA,
    },
    "set_charger_ocpp": {
        "handler": charger_execute_set_ocpp,
        "function_call": "set_ocpp_config",
        "function_call_2": "apply_ocpp_config",
        "schema": SERVICE_SET_OCPP,
    },
    "set_operator": {
        "handler": charger_execute_set_operator,
        "function_call": "set_operator",
        "schema": SERVICE_SET_OPERATOR,
    },
}


async def async_setup_services(hass: HomeAssistant):
    """Set up services for Easee."""

    for service, data in SERVICE_MAP.items():
        handler = data["handler"]
        hass.services.async_register(DOMAIN, service, handler, schema=data["schema"])
