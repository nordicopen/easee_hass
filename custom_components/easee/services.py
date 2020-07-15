""" easee services."""
import voluptuous as vol
import logging
from homeassistant.helpers import config_validation as cv
from homeassistant.exceptions import HomeAssistantError

DOMAIN = "easee"
_LOGGER = logging.getLogger(__name__)
CHARGER_ID = "charger_id"
# COMMAND_START = "start"
ATTR_CHARGEPLAN_START_TIME = "chargeStartTime"
ATTR_CHARGEPLAN_STOP_TIME = "chargeStopTime"
ATTR_CHARGEPLAN_REPEAT = "repeat"

SERVICE_CHARGER_ACTION_COMMAND_SCHEMA = vol.Schema(
    {vol.Optional(CHARGER_ID): cv.string,}
)

SERVICE_CHARGER_SET_BASIC_CHARGEPLAN_SCHEMA = vol.Schema(
    {
        vol.Required(CHARGER_ID): cv.string,
        vol.Optional(ATTR_CHARGEPLAN_START_TIME): cv.time,
        vol.Optional(ATTR_CHARGEPLAN_STOP_TIME): cv.time,
        vol.Optional(ATTR_CHARGEPLAN_REPEAT): cv.boolean,
    }
)

SERVICE_MAP = {
    "start": {
        "function_call": "start",
        "schema": SERVICE_CHARGER_ACTION_COMMAND_SCHEMA,
    },
    "stop": {"function_call": "stop", "schema": SERVICE_CHARGER_ACTION_COMMAND_SCHEMA,},
    "pause": {
        "function_call": "pause",
        "schema": SERVICE_CHARGER_ACTION_COMMAND_SCHEMA,
    },
    "resume": {
        "function_call": "resume",
        "schema": SERVICE_CHARGER_ACTION_COMMAND_SCHEMA,
    },
    "toggle": {
        "function_call": "toggle",
        "schema": SERVICE_CHARGER_ACTION_COMMAND_SCHEMA,
    },
    "override_schedule": {
        "function_call": "override_schedule",
        "schema": SERVICE_CHARGER_ACTION_COMMAND_SCHEMA,
    },
    "smart_charging": {
        "function_call": "smart_charging",
        "schema": SERVICE_CHARGER_ACTION_COMMAND_SCHEMA,
    },
    "reboot": {
        "function_call": "reboot",
        "schema": SERVICE_CHARGER_ACTION_COMMAND_SCHEMA,
    },
    "update_firmware": {
        "function_call": "update_firmware",
        "schema": SERVICE_CHARGER_ACTION_COMMAND_SCHEMA,
    },
    "get_basic_charge_plan": {
        "function_call": "get_basic_charge_plan",
        "schema": SERVICE_CHARGER_ACTION_COMMAND_SCHEMA,
    },
    "set_basic_charge_plan": {
        "function_call": "get_basic_charge_plan",
        "schema": SERVICE_CHARGER_SET_BASIC_CHARGEPLAN_SCHEMA,
    },
    "delete_basic_charge_plan": {
        "function_call": "get_basic_charge_plan",
        "schema": SERVICE_CHARGER_ACTION_COMMAND_SCHEMA,
    },
}


async def async_setup_services(hass):
    """ Setup services for Easee """

    if "easee" not in hass.data[DOMAIN]:
        easee = Easee(username, password)
        hass.data[DOMAIN] = {"easee": easee}
    else:
        easee = hass.data[DOMAIN]["easee"]

    async def execute_service(call):
        """Execute a service to Easee charging station. """
        charger_id = call.data.get(CHARGER_ID)
        chargers = hass.data[DOMAIN]["chargers"]

        _LOGGER.info("TEST:" + str(call.data))

        # Move to use entity id later
        charger = next((c for c in chargers if c.id == charger_id), None)
        if charger:
            function_name = SERVICE_MAP[call.service]
            function_call = getattr(charger, function_name["function_call"])
            return await function_call()
        _LOGGER.error(
            "Could not find charger %s", charger_id,
        )
        raise HomeAssistantError("Could not find charger {}".format(charger_id))

    for service in SERVICE_MAP:
        data = SERVICE_MAP[service]
        hass.services.async_register(
            DOMAIN, service, execute_service, schema=data["schema"],
        )

    # async def start_charger(call):
    #     """Start charger."""
    #     charger_id = call.data.get(CHARGER_ID)
    #     chargers = hass.data[DOMAIN]["chargers"]
    #     # Move to use entity id later
    #     charger = next((c for c in chargers if c.id == charger_id), None)
    #     if charger:
    #         return await charger.start()
    #     _LOGGER.error(
    #         "Could not find charger %s", charger_id,
    #     )
    #     raise HomeAssistantError("Could not find charger {}".format(charger_id))

    # hass.services.async_register(
    #     DOMAIN, COMMAND_START, start_charger, schema=SERVICE_CHARGER_ACTION_COMMAND_SCHEMA,
    # )

