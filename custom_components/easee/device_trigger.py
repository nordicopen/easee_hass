"""Provides device automations for Easee."""
import logging
from typing import List

import voluptuous as vol
from homeassistant.components.automation import AutomationActionType
from homeassistant.components.device_automation import TRIGGER_BASE_SCHEMA
from homeassistant.components.homeassistant.triggers import state
from homeassistant.const import (
    CONF_DEVICE_ID,
    CONF_DOMAIN,
    CONF_ENTITY_ID,
    CONF_PLATFORM,
    CONF_TYPE,
)
from homeassistant.core import CALLBACK_TYPE, HomeAssistant
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers import entity_registry
from homeassistant.helpers.typing import ConfigType

from .const import (
    DOMAIN,
    EA_AWAITING_START,
    EA_CHARGING,
    EA_COMPLETED,
    EA_DISCONNECTED,
    EA_ERROR,
    EA_READY_TO_CHARGE,
)

_LOGGER = logging.getLogger(__name__)

EA_STATES = [
    EA_AWAITING_START,
    EA_DISCONNECTED,
    EA_CHARGING,
    EA_COMPLETED,
    EA_ERROR,
    EA_READY_TO_CHARGE,
]

# TODO specify your supported trigger types.
TRIGGER_TYPES = {
    "charging_started",
    "charging_completed",
    "car_disconnected",
    "awaiting_start",
    "ready_to_charge",
    "error",
}

TRIGGER_SCHEMA = TRIGGER_BASE_SCHEMA.extend(
    {
        vol.Required(CONF_ENTITY_ID): cv.entity_id,
        vol.Required(CONF_TYPE): vol.In(TRIGGER_TYPES),
    }
)


async def async_get_triggers(hass: HomeAssistant, device_id: str) -> List[dict]:
    """List device triggers for Easee devices."""
    registry = await entity_registry.async_get_registry(hass)
    triggers = []
    _LOGGER.info("async_get_triggers()")

    # Get all the integrations entities for this device
    for entry in entity_registry.async_entries_for_device(registry, device_id):
        _LOGGER.debug("Entities: %s - %s", entry.domain, entry.entity_id)
        if entry.domain != DOMAIN and entry.device_class != "easee_status":
            continue

        # Add triggers for each entity that belongs to this integration
        _LOGGER.debug("Append triggers to: %s - %s", entry.domain, entry.entity_id)
        triggers.append(
            {
                CONF_PLATFORM: "device",
                CONF_DEVICE_ID: device_id,
                CONF_DOMAIN: DOMAIN,
                CONF_ENTITY_ID: entry.entity_id,
                CONF_TYPE: "charging_started",
            }
        )
        triggers.append(
            {
                CONF_PLATFORM: "device",
                CONF_DEVICE_ID: device_id,
                CONF_DOMAIN: DOMAIN,
                CONF_ENTITY_ID: entry.entity_id,
                CONF_TYPE: "charging_completed",
            }
        )
        triggers.append(
            {
                CONF_PLATFORM: "device",
                CONF_DEVICE_ID: device_id,
                CONF_DOMAIN: DOMAIN,
                CONF_ENTITY_ID: entry.entity_id,
                CONF_TYPE: "car_disconnected",
            }
        )
        triggers.append(
            {
                CONF_PLATFORM: "device",
                CONF_DEVICE_ID: device_id,
                CONF_DOMAIN: DOMAIN,
                CONF_ENTITY_ID: entry.entity_id,
                CONF_TYPE: "awaiting_start",
            }
        )
        triggers.append(
            {
                CONF_PLATFORM: "device",
                CONF_DEVICE_ID: device_id,
                CONF_DOMAIN: DOMAIN,
                CONF_ENTITY_ID: entry.entity_id,
                CONF_TYPE: "ready_to_charge",
            }
        )
        triggers.append(
            {
                CONF_PLATFORM: "device",
                CONF_DEVICE_ID: device_id,
                CONF_DOMAIN: DOMAIN,
                CONF_ENTITY_ID: entry.entity_id,
                CONF_TYPE: "error",
            }
        )

    return triggers


async def async_attach_trigger(
    hass: HomeAssistant,
    config: ConfigType,
    action: AutomationActionType,
    automation_info: dict,
) -> CALLBACK_TYPE:
    """Attach a trigger."""
    config = TRIGGER_SCHEMA(config)

    # TODO Implement your own logic to attach triggers.
    # Generally we suggest to re-use the existing state or event
    # triggers from the automation integration.

    if config[CONF_TYPE] == "charging_started":
        from_state = [state for state in EA_STATES if state != EA_CHARGING]
        to_state = EA_CHARGING
    elif config[CONF_TYPE] == "charging_completed":
        from_state = [state for state in EA_STATES if state != EA_COMPLETED]
        to_state = EA_COMPLETED
    elif config[CONF_TYPE] == "car_disconnected":
        from_state = [state for state in EA_STATES if state != EA_DISCONNECTED]
        to_state = EA_DISCONNECTED
    elif config[CONF_TYPE] == "awaiting_start":
        from_state = [state for state in EA_STATES if state != EA_AWAITING_START]
        to_state = EA_AWAITING_START
    elif config[CONF_TYPE] == "ready_to_charge":
        from_state = [state for state in EA_STATES if state != EA_READY_TO_CHARGE]
        to_state = EA_READY_TO_CHARGE
    elif config[CONF_TYPE] == "error":
        from_state = [state for state in EA_STATES if state != EA_ERROR]
        to_state = EA_ERROR

    state_config = {
        state.CONF_PLATFORM: "state",
        CONF_ENTITY_ID: config[CONF_ENTITY_ID],
        state.CONF_FROM: from_state,
        state.CONF_TO: to_state,
    }
    state_config = state.TRIGGER_SCHEMA(state_config)
    return await state.async_attach_trigger(
        hass, state_config, action, automation_info, platform_type="device"
    )
