"""Provide info to system health."""
from homeassistant.components import system_health
from homeassistant.core import HomeAssistant, callback

from .const import DOMAIN, VERSION


@callback
def async_register(
    hass: HomeAssistant, register: system_health.SystemHealthRegistration
) -> None:
    """Register system health callbacks."""
    register.async_register_info(system_health_info)


async def system_health_info(hass):
    """Get info for the info page."""
    client = hass.data[DOMAIN]

    return {
        "component_version": VERSION,
        "reach_easee_cloud": system_health.async_check_can_reach_url(
            hass, client["controller"].easee.base_uri()
        ),
        "connected2stream": client["controller"].easee.sr_is_connected(),
    }
