"""Provides device actions for easee_hass."""
from __future__ import annotations

import voluptuous as vol

from homeassistant.const import (
    ATTR_DEVICE_ID,
    CONF_DEVICE_ID,
    CONF_DOMAIN,
    CONF_TYPE,
)
from homeassistant.core import Context, HomeAssistant
from homeassistant.helpers import config_validation as cv, entity_registry as er

from . import DOMAIN

ACTION_TYPES = {
    "override_schedule",
    "pause",
    "reboot",
    "resume",
    "start",
    "stop",
    "toggle",
}

ACTION_SCHEMA = cv.DEVICE_ACTION_BASE_SCHEMA.extend(
    {
        vol.Required(CONF_TYPE): vol.In(ACTION_TYPES),
        vol.Required(CONF_DEVICE_ID): str,
    }
)


async def async_get_actions(
    hass: HomeAssistant, device_id: str
) -> list[dict[str, str]]:
    """List device actions for easee_hass devices."""
    registry = er.async_get(hass)
    actions = []

    # Get all the integrations entities for this device
    for entry in er.async_entries_for_device(registry, device_id):
        if entry.translation_key == "easee_status":
            # Add actions for each entity that belongs to this integration
            base_action = {
                CONF_DEVICE_ID: device_id,
                CONF_DOMAIN: DOMAIN,
            }

            actions += [{**base_action, CONF_TYPE: act} for act in ACTION_TYPES]

    return actions


async def async_call_action_from_config(
    hass: HomeAssistant, config: dict, variables: dict, context: Context | None
) -> None:
    """Execute a device action."""
    service_data = {
        ATTR_DEVICE_ID: config[CONF_DEVICE_ID],
        "action_command": config[CONF_TYPE],
    }

    service = "action_command"

    await hass.services.async_call(
        DOMAIN, service, service_data, blocking=True, context=context
    )
