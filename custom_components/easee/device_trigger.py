"""Provides device automations for Easee."""
from typing import List

import voluptuous as vol

from homeassistant.components.automation import AutomationActionType
from homeassistant.components.device_automation import TRIGGER_BASE_SCHEMA
from homeassistant.components.homeassistant.triggers import state as state_trigger
from homeassistant.const import (
    CONF_DEVICE_ID,
    CONF_DOMAIN,
    CONF_ENTITY_ID,
    CONF_PLATFORM,
    CONF_TYPE,
)
from homeassistant.core import CALLBACK_TYPE, HomeAssistant
from homeassistant.helpers import config_validation as cv, entity_registry
from homeassistant.helpers.typing import ConfigType

from .const import DOMAIN, EA_DISCONNECTED, EA_CHARGING, EA_COMPLETED, EASEE_STATUS

TRIGGER_TYPES = {EA_DISCONNECTED, EA_CHARGING, EA_COMPLETED}

TRIGGER_SCHEMA = TRIGGER_BASE_SCHEMA.extend(
    {
        vol.Required(CONF_ENTITY_ID): cv.entity_id,
        vol.Required(CONF_TYPE): vol.In(TRIGGER_TYPES),
    }
)


async def async_get_triggers(hass: HomeAssistant, device_id: str) -> List[dict]:
    """List device triggers for Easeee devices."""
    registry = await entity_registry.async_get_registry(hass)
    triggers = []

    # Get all the integrations entities for this device
    for entry in entity_registry.async_entries_for_device(registry, device_id):
        if entry.domain != DOMAIN:
            continue

        triggers.append(
            {
                CONF_PLATFORM: "device",
                CONF_DEVICE_ID: device_id,
                CONF_DOMAIN: DOMAIN,
                CONF_ENTITY_ID: entry.entity_id,
                CONF_TYPE: EA_DISCONNECTED,
            }
        )
        triggers.append(
            {
                CONF_PLATFORM: "device",
                CONF_DEVICE_ID: device_id,
                CONF_DOMAIN: DOMAIN,
                CONF_ENTITY_ID: entry.entity_id,
                CONF_TYPE: EA_CHARGING,
            }
        )
        triggers.append(
            {
                CONF_PLATFORM: "device",
                CONF_DEVICE_ID: device_id,
                CONF_DOMAIN: DOMAIN,
                CONF_ENTITY_ID: entry.entity_id,
                CONF_TYPE: EA_COMPLETED,
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

    if config[CONF_TYPE] == EA_DISCONNECTED:
        from_state = [state for state in EASEE_STATUS if state != EA_DISCONNECTED]
        to_state = EA_DISCONNECTED
    else:
        from_state = [state for state in EASEE_STATUS if state != EA_CHARGING]
        to_state = EA_CHARGING

    state_config = {
        CONF_PLATFORM: "state",
        CONF_ENTITY_ID: config[CONF_ENTITY_ID],
        state_trigger.CONF_FROM: from_state,
        state_trigger.CONF_TO: to_state,
    }
    state_config = state_trigger.TRIGGER_SCHEMA(state_config)
    return await state_trigger.async_attach_trigger(
        hass, state_config, action, automation_info, platform_type="device"
    )
