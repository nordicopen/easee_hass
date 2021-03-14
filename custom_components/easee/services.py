""" easee services."""
import logging

import voluptuous as vol
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import config_validation as cv
from homeassistant.util import dt

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

ACCESS_LEVEL = "access_level"
CHARGER_ID = "charger_id"
CIRCUIT_ID = "circuit_id"
ATTR_CHARGEPLAN_START_DATETIME = "start_datetime"
ATTR_CHARGEPLAN_STOP_DATETIME = "stop_datetime"
ATTR_CHARGEPLAN_REPEAT = "repeat"
ATTR_SET_CURRENT = "current"
ATTR_SET_CURRENTP1 = "currentP1"
ATTR_SET_CURRENTP2 = "currentP2"
ATTR_SET_CURRENTP3 = "currentP3"
ATTR_COST_PER_KWH = "cost_per_kwh"
ATTR_COST_CURRENCY = "currency_id"
ATTR_COST_VAT = "vat"

SERVICE_CHARGER_ACTION_COMMAND_SCHEMA = vol.Schema(
    {vol.Optional(CHARGER_ID): cv.string}
)

SERVICE_CHARGER_SET_BASIC_CHARGEPLAN_SCHEMA = vol.Schema(
    {
        vol.Required(CHARGER_ID): cv.string,
        vol.Optional(ATTR_CHARGEPLAN_START_DATETIME): cv.datetime,
        vol.Optional(ATTR_CHARGEPLAN_STOP_DATETIME): cv.datetime,
        vol.Optional(ATTR_CHARGEPLAN_REPEAT): cv.boolean,
    }
)

SERVICE_SET_CHARGER_CIRCUIT_CURRENT_SCHEMA = vol.Schema(
    {
        vol.Required(CHARGER_ID): cv.string,
        vol.Required(ATTR_SET_CURRENTP1): cv.positive_int,
        vol.Optional(ATTR_SET_CURRENTP2): cv.positive_int,
        vol.Optional(ATTR_SET_CURRENTP3): cv.positive_int,
    }
)

SERVICE_SET_CHARGER_CURRENT_SCHEMA = vol.Schema(
    {
        vol.Required(CHARGER_ID): cv.string,
        vol.Required(ATTR_SET_CURRENT): cv.positive_int,
    }
)

SERVICE_SET_SITE_CHARGING_COST_SCHEMA = vol.Schema(
    {
        vol.Required(CHARGER_ID): cv.string,
        vol.Required(ATTR_COST_PER_KWH): vol.All(vol.Coerce(float)),
        vol.Optional(ATTR_COST_CURRENCY): cv.string,
        vol.Optional(ATTR_COST_VAT): vol.All(vol.Coerce(float)),
    }
)


SERVICE_SET_ACCESS_SHCEMA = vol.Schema(
    {vol.Required(CHARGER_ID): cv.string, vol.Required(ACCESS_LEVEL): vol.Any(int, str)}
)


SERVICE_MAP = {
    "start": {
        "handler": "charger_execute_service",
        "function_call": "start",
        "schema": SERVICE_CHARGER_ACTION_COMMAND_SCHEMA,
    },
    "stop": {
        "handler": "charger_execute_service",
        "function_call": "stop",
        "schema": SERVICE_CHARGER_ACTION_COMMAND_SCHEMA,
    },
    "pause": {
        "handler": "charger_execute_service",
        "function_call": "pause",
        "schema": SERVICE_CHARGER_ACTION_COMMAND_SCHEMA,
    },
    "resume": {
        "handler": "charger_execute_service",
        "function_call": "resume",
        "schema": SERVICE_CHARGER_ACTION_COMMAND_SCHEMA,
    },
    "toggle": {
        "handler": "charger_execute_service",
        "function_call": "toggle",
        "schema": SERVICE_CHARGER_ACTION_COMMAND_SCHEMA,
    },
    "override_schedule": {
        "handler": "charger_execute_service",
        "function_call": "override_schedule",
        "schema": SERVICE_CHARGER_ACTION_COMMAND_SCHEMA,
    },
    "smart_charging": {
        "handler": "charger_execute_service",
        "function_call": "smart_charging",
        "schema": SERVICE_CHARGER_ACTION_COMMAND_SCHEMA,
    },
    "reboot": {
        "handler": "charger_execute_service",
        "function_call": "reboot",
        "schema": SERVICE_CHARGER_ACTION_COMMAND_SCHEMA,
    },
    "update_firmware": {
        "handler": "charger_execute_service",
        "function_call": "update_firmware",
        "schema": SERVICE_CHARGER_ACTION_COMMAND_SCHEMA,
    },
    "set_basic_charge_plan": {
        "handler": "charger_set_schedule",
        "function_call": "set_basic_charge_plan",
        "schema": SERVICE_CHARGER_SET_BASIC_CHARGEPLAN_SCHEMA,
    },
    "delete_basic_charge_plan": {
        "handler": "charger_execute_service",
        "function_call": "delete_basic_charge_plan",
        "schema": SERVICE_CHARGER_ACTION_COMMAND_SCHEMA,
    },
    "set_charger_circuit_dynamic_limit": {
        "handler": "charger_execute_set_circuit_current",
        "function_call": "set_dynamic_charger_circuit_current",
        "schema": SERVICE_SET_CHARGER_CIRCUIT_CURRENT_SCHEMA,
    },
    "set_charger_circuit_max_limit": {
        "handler": "charger_execute_set_circuit_current",
        "function_call": "set_max_charger_circuit_current",
        "schema": SERVICE_SET_CHARGER_CIRCUIT_CURRENT_SCHEMA,
    },
    "set_charger_dynamic_limit": {
        "handler": "charger_execute_set_current",
        "function_call": "set_dynamic_charger_current",
        "schema": SERVICE_SET_CHARGER_CURRENT_SCHEMA,
    },
    "set_charger_max_limit": {
        "handler": "charger_execute_set_current",
        "function_call": "set_max_charger_current",
        "schema": SERVICE_SET_CHARGER_CURRENT_SCHEMA,
    },
    "set_charging_cost": {
        "handler": "charger_execute_set_charging_cost",
        "function_call": "set_price",
        "schema": SERVICE_SET_SITE_CHARGING_COST_SCHEMA,
    },
    "set_charger_access": {
        "handler": "charger_execute_set_access",
        "function_call": "set_access",
        "schema": SERVICE_SET_ACCESS_SHCEMA,
    },
}


async def async_setup_services(hass):
    """Setup services for Easee."""
    controller = hass.data[DOMAIN]["controller"]
    chargers = controller.get_chargers()
    circuits = controller.get_circuits()

    async def charger_execute_service(call):
        """Execute a service to Easee charging station."""
        charger_id = call.data.get(CHARGER_ID)

        _LOGGER.debug("execute_service:" + str(call.data))

        # Possibly move to use entity id later
        charger = next((c for c in chargers if c.id == charger_id), None)
        if charger:
            function_name = SERVICE_MAP[call.service]
            function_call = getattr(charger, function_name["function_call"])
            return await function_call()

        _LOGGER.error("Could not find charger %s", charger_id)
        raise HomeAssistantError("Could not find charger {}".format(charger_id))

    async def charger_set_schedule(call):
        """Execute a set schedule call to Easee charging station."""
        charger_id = call.data.get(CHARGER_ID)
        schedule_id = charger_id  # future versions of Easee API will allow multiple schedules, i.e. work-in-progress
        start_datetime = call.data.get(ATTR_CHARGEPLAN_START_DATETIME)
        stop_datetime = call.data.get(ATTR_CHARGEPLAN_STOP_DATETIME)
        repeat = call.data.get(ATTR_CHARGEPLAN_REPEAT)

        _LOGGER.debug("execute_service:" + str(call.data))

        charger = next((c for c in chargers if c.id == charger_id), None)
        if charger:
            function_name = SERVICE_MAP[call.service]
            function_call = getattr(charger, function_name["function_call"])
            return await function_call(
                schedule_id, dt.as_utc(start_datetime), dt.as_utc(stop_datetime), repeat
            )

        _LOGGER.error("Could not find charger %s", charger_id)
        raise HomeAssistantError("Could not find charger {}".format(charger_id))

    async def charger_execute_set_circuit_current(call):
        """Execute a service to set currents for Easee circuit for specific charger."""
        charger_id = call.data.get(CHARGER_ID)
        currentP1 = call.data.get(ATTR_SET_CURRENTP1)
        currentP2 = call.data.get(ATTR_SET_CURRENTP2)
        currentP3 = call.data.get(ATTR_SET_CURRENTP3)

        _LOGGER.debug("execute_service:" + str(call.data))

        charger = next((c for c in chargers if c.id == charger_id), None)
        if charger:
            function_name = SERVICE_MAP[call.service]
            function_call = getattr(charger, function_name["function_call"])
            return await function_call(currentP1, currentP2, currentP3)

        _LOGGER.error("Could not find charger %s", charger_id)
        raise HomeAssistantError("Could not find charger {}".format(charger_id))

    async def charger_execute_set_current(call):
        """Execute a service to set currents for Easee charger."""
        charger_id = call.data.get(CHARGER_ID)
        current = call.data.get(ATTR_SET_CURRENT)

        _LOGGER.debug("execute_service:" + str(call.data))

        charger = next((c for c in chargers if c.id == charger_id), None)
        if charger:
            function_name = SERVICE_MAP[call.service]
            function_call = getattr(charger, function_name["function_call"])
            return await function_call(current)

        _LOGGER.error("Could not find charger %s", charger_id)
        raise HomeAssistantError("Could not find charger {}".format(charger_id))

    async def charger_execute_set_charging_cost(call):
        """Execute a service to set charging cost per kwh for Easee charger site."""
        charger_id = call.data.get(CHARGER_ID)
        cost_per_kwh = call.data.get(ATTR_COST_PER_KWH)
        currency = call.data.get(ATTR_COST_CURRENCY)
        vat = call.data.get(ATTR_COST_VAT)

        _LOGGER.debug("execute_service:" + str(call.data))

        charger = next((c for c in chargers if c.id == charger_id), None)
        if charger:
            function_name = SERVICE_MAP[call.service]
            function_call = getattr(charger.site, function_name["function_call"])
            return await function_call(cost_per_kwh, vat, currency)

        _LOGGER.error("Could not find charger %s", charger_id)
        raise HomeAssistantError("Could not find charger {}".format(charger_id))

    async def charger_execute_set_access(call):
        """Execute a service to set access level on a charger"""
        charger_id = call.data.get(CHARGER_ID)
        access_level = call.data.get(ACCESS_LEVEL)

        _LOGGER.debug("execute_service:" + str(call.data))

        charger = next((c for c in chargers if c.id == charger_id), None)
        if charger:
            function_name = SERVICE_MAP[call.service]
            function_call = getattr(charger, function_name["function_call"])
            return await function_call(access_level)

    for service in SERVICE_MAP:
        data = SERVICE_MAP[service]
        handler = locals()[data["handler"]]
        hass.services.async_register(DOMAIN, service, handler, schema=data["schema"])
