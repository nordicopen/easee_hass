"""Provides device automations for Easee EV Charger."""
from typing import List, Optional

import voluptuous as vol

from homeassistant.const import (
    ATTR_CODE,
    #    ATTR_ENTITY_ID,
    #    ATTR_SUPPORTED_FEATURES,
    CONF_CODE,
    CONF_DEVICE_ID,
    CONF_DOMAIN,
    CONF_ENTITY_ID,
    CONF_TYPE,
    #    SERVICE_ALARM_ARM_AWAY,
    #    SERVICE_ALARM_ARM_HOME,
    #    SERVICE_ALARM_ARM_NIGHT,
    #    SERVICE_ALARM_DISARM,
    #    SERVICE_ALARM_TRIGGER,
)
from homeassistant.core import Context, HomeAssistant
from homeassistant.helpers import entity_registry
import homeassistant.helpers.config_validation as cv

from .const import (
    DOMAIN,
)

ACTION_TYPES = {"charger_start", "charger_stop", "charger_pause", "charger_resume", "charger_toggle"}

ACTION_SCHEMA = cv.DEVICE_ACTION_BASE_SCHEMA.extend(
    {
        vol.Required(CONF_TYPE): vol.In(ACTION_TYPES),
        vol.Required(CONF_ENTITY_ID): cv.entity_domain(DOMAIN),
    }
)


async def async_get_actions(hass: HomeAssistant, device_id: str) -> List[dict]:
    """List device actions for Alarm control panel devices."""
    registry = await entity_registry.async_get_registry(hass)
    actions = []

    # Get all the integrations entities for this device
    for entry in entity_registry.async_entries_for_device(registry, device_id):
        if entry.domain != DOMAIN and entry.device_class != "easee_status":
            continue

        # if state is None:
        #     continue

        # supported_features = state.attributes[ATTR_SUPPORTED_FEATURES]

        # Add actions for each entity that belongs to this integration
        actions.append(
            {
                CONF_DEVICE_ID: device_id,
                CONF_DOMAIN: DOMAIN,
                CONF_ENTITY_ID: entry.entity_id,
                CONF_TYPE: "charger_start",
            }
        )
        actions.append(
            {
                CONF_DEVICE_ID: device_id,
                CONF_DOMAIN: DOMAIN,
                CONF_ENTITY_ID: entry.entity_id,
                CONF_TYPE: "charger_stop",
            }
        )
        actions.append(
            {
                CONF_DEVICE_ID: device_id,
                CONF_DOMAIN: DOMAIN,
                CONF_ENTITY_ID: entry.entity_id,
                CONF_TYPE: "charger_pause",
            }
        )
        actions.append(
            {
                CONF_DEVICE_ID: device_id,
                CONF_DOMAIN: DOMAIN,
                CONF_ENTITY_ID: entry.entity_id,
                CONF_TYPE: "charger_resume",
            }
        )
        actions.append(
            {
                CONF_DEVICE_ID: device_id,
                CONF_DOMAIN: DOMAIN,
                CONF_ENTITY_ID: entry.entity_id,
                CONF_TYPE: "charger_toggle",
            }
        )

    return actions


async def async_call_action_from_config(
    hass: HomeAssistant, config: dict, variables: dict, context: Optional[Context]
) -> None:
    """Execute a device action."""
    config = ACTION_SCHEMA(config)

    service_data = {"charger_id": "EH468215"}  # config[CONF_ENTITY_ID]}
    if CONF_CODE in config:
        service_data[ATTR_CODE] = config[CONF_CODE]

    if config[CONF_TYPE] == "charger_start":
        service = "easee.start"
    elif config[CONF_TYPE] == "charger_stop":
        service = "easee.stop"
    elif config[CONF_TYPE] == "charger_pause":
        service = "easee_pause"
    elif config[CONF_TYPE] == "charger_resume":
        service = "easee.resume"
    elif config[CONF_TYPE] == "charger_toggle":
        service = "easee.toggle"

    await hass.services.async_call(
        DOMAIN, service, service_data, blocking=True, context=context
    )


# async def async_get_action_capabilities(hass, config):
#     """List action capabilities."""
#     state = hass.states.get(config[CONF_ENTITY_ID])
#     code_required = state.attributes.get(ATTR_CODE_ARM_REQUIRED) if state else False

#     if config[CONF_TYPE] == "trigger" or (
#         config[CONF_TYPE] != "disarm" and not code_required
#     ):
#         return {}

#     return {"extra_fields": vol.Schema({vol.Optional(CONF_CODE): str})}
