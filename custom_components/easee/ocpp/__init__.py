"""Local OCPP 1.6J central system for Easee chargers, hosted inside Home Assistant."""

from __future__ import annotations

from collections.abc import Callable, Iterable

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import Entity
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from ..const import DOMAIN
from .authorization import RfidAuthorizer
from .cloud_setup import EaseeOcppCloud
from .const import (
    CONF_ALLOWED_ID_TAGS,
    CONF_OCPP_PASSWORD,
    CONF_SERIAL,
    SUBENTRY_TYPE_OCPP_CHARGER,
)
from .health import OcppHealthMonitor
from .hub import OcppChargerConfig, OcppHub
from .models import Serial
from .removal import async_release_removed_chargers
from .server import HUB_DATA_KEY, OcppWebSocketView


def async_register_ocpp_view(hass: HomeAssistant) -> None:
    """Register the websocket endpoint once; it finds the current hub at request time."""
    hass.http.register_view(OcppWebSocketView())


def ocpp_charger_configs(entry: ConfigEntry) -> list[OcppChargerConfig]:
    """Return the chargers that have an OCPP subentry."""
    return [
        OcppChargerConfig(
            serial=subentry.data[CONF_SERIAL],
            password=subentry.data[CONF_OCPP_PASSWORD],
        )
        for subentry in entry.subentries.values()
        if subentry.subentry_type == SUBENTRY_TYPE_OCPP_CHARGER
    ]


async def async_setup_ocpp_hub(hass: HomeAssistant, entry: ConfigEntry) -> OcppHub:
    """Create the hub for the chargers of this config entry."""
    hub = OcppHub(hass, ocpp_charger_configs(entry), RfidAuthorizer(hass, entry))
    await hub.async_load()
    cloud = EaseeOcppCloud(hass.data[DOMAIN]["controller"].easee)
    await async_release_removed_chargers(hass, entry, set(hub.serials()), cloud)
    await OcppHealthMonitor(hass, entry, hub).async_start()
    hass.data[HUB_DATA_KEY] = hub
    return hub


async def async_unload_ocpp_hub(hass: HomeAssistant) -> None:
    """Close all OCPP connections."""
    hub: OcppHub | None = hass.data.pop(HUB_DATA_KEY, None)
    if hub is not None:
        await hub.async_shutdown()


def async_add_ocpp_entities(
    hass: HomeAssistant,
    async_add_entities: AddConfigEntryEntitiesCallback,
    entities_for_charger: Callable[[OcppHub, Serial], Iterable[Entity]],
) -> None:
    """Add the OCPP entities of every charger.

    They deliberately belong to no subentry: since HA 2026.11 a device belongs to exactly
    one subentry, and the cloud entities of the same charger device belong to none.
    Mixing both moves the device back and forth and HA deletes the other side's entities.
    """
    hub = get_ocpp_hub(hass)
    if hub is None:
        return
    for serial in hub.serials():
        async_add_entities(entities_for_charger(hub, serial))


type ReloadRelevantSettings = tuple[object, ...]


def reload_relevant_settings(entry: ConfigEntry) -> ReloadRelevantSettings:
    """Everything whose change needs a reload; the RFID whitelist is read live and is not part of it."""
    options = {
        key: value
        for key, value in entry.options.items()
        if key != CONF_ALLOWED_ID_TAGS
    }
    subentries = {
        subentry_id: (subentry.subentry_type, dict(subentry.data))
        for subentry_id, subentry in entry.subentries.items()
    }
    return (dict(entry.data), options, subentries)


def get_ocpp_hub(hass: HomeAssistant) -> OcppHub | None:
    """Return the hub of the loaded config entry."""
    hub: OcppHub | None = hass.data.get(HUB_DATA_KEY)
    return hub
