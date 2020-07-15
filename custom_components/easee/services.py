""" easee services."""
import voluptuous as vol
from homeassistant.helpers import config_validation as cv

DOMAIN = "easee"
CHARGER_ID = "charger_id"
COMMAND_START = "start"
COMMAND_STOP = "stop"
COMMAND_PAUSE = "pause"
COMMAND_RESUME = "resume"

SERVICE_CHARGER_ACTION_COMMAND_SCHEMA = vol.Schema({vol.Optional(CHARGER_ID): cv.string,})


async def async_setup_services(hass):
    """ Setup services for Easee """

    async def start_charger(call):
        """Start charger."""
        charger_id = call.data.get(CHARGER_ID)
        chargers = hass.data[DOMAIN]["chargers"]
        # Move to use entity id later
        charger = next((c for c in chargers if c.id == charger_id), None)
        if charger:
            return await charger.start()
        _LOGGER.error(
            "Could not find charger %s", charger_id,
        )
        raise HomeAssistantError("Could not find charger {}".format(charger_id))

    async def stop_charger(call):
        """Stop charger."""
        charger_id = call.data.get(CHARGER_ID)
        chargers = hass.data[DOMAIN]["chargers"]
        # Move to use entity id later
        charger = next((c for c in chargers if c.id == charger_id), None)
        if charger:
            return await charger.stop()
        _LOGGER.error(
            "Could not find charger %s", charger_id,
        )
        raise HomeAssistantError("Could not find charger {}".format(charger_id))

    async def pause_charger(call):
        """Pause charger."""
        charger_id = call.data.get(CHARGER_ID)
        chargers = hass.data[DOMAIN]["chargers"]
        # Move to use entity id later
        charger = next((c for c in chargers if c.id == charger_id), None)
        if charger:
            return await charger.pause()
        _LOGGER.error(
            "Could not find charger %s", charger_id,
        )
        raise HomeAssistantError("Could not find charger {}".format(charger_id))

    async def resume_charger(call):
        """Resume charger."""
        charger_id = call.data.get(CHARGER_ID)
        chargers = hass.data[DOMAIN]["chargers"]
        # Move to use entity id later
        charger = next((c for c in chargers if c.id == charger_id), None)
        if charger:
            return await charger.resume()
        _LOGGER.error(
            "Could not find charger %s", charger_id,
        )
        raise HomeAssistantError("Could not find charger {}".format(charger_id))

    
    hass.services.async_register(
        DOMAIN, COMMAND_START, start_charger, schema=SERVICE_CHARGER_ACTION_COMMAND_SCHEMA,
    )
    hass.services.async_register(
        DOMAIN, COMMAND_STOP, stop_charger, schema=SERVICE_CHARGER_ACTION_COMMAND_SCHEMA,
    )
    hass.services.async_register(
        DOMAIN, COMMAND_PAUSE, pause_charger, schema=SERVICE_CHARGER_ACTION_COMMAND_SCHEMA,
    )
    hass.services.async_register(
        DOMAIN, COMMAND_RESUME, resume_charger, schema=SERVICE_CHARGER_ACTION_COMMAND_SCHEMA,
    )
