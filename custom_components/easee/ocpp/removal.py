"""Clean up after an OCPP subentry was deleted."""

from __future__ import annotations

import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.storage import Store

from .cloud_setup import EaseeOcppCloud, OcppCloudError
from .const import OCPP_UNIQUE_ID_MARKER, OCPP_VIEW_BASE_PATH
from .models import Serial

_LOGGER = logging.getLogger(__name__)

STORAGE_KEY = "easee_ocpp_chargers"
STORAGE_VERSION = 1


def is_ocpp_unique_id_of_other_charger(
    unique_id: str, configured_serials: set[Serial]
) -> bool:
    """Return True for an OCPP entity whose charger no longer has a subentry."""
    serial, separator, _ = unique_id.partition(OCPP_UNIQUE_ID_MARKER)
    return bool(separator) and serial not in configured_serials


def remove_entities_of_removed_chargers(
    hass: HomeAssistant, entry: ConfigEntry, configured_serials: set[Serial]
) -> None:
    """Delete OCPP entities of chargers without subentry.

    HA cannot do this itself because the OCPP entities belong to no subentry (see
    async_add_ocpp_entities).
    """
    registry = er.async_get(hass)
    for registry_entry in er.async_entries_for_config_entry(registry, entry.entry_id):
        if is_ocpp_unique_id_of_other_charger(
            registry_entry.unique_id, configured_serials
        ):
            registry.async_remove(registry_entry.entity_id)


def points_to_home_assistant(url: str | None) -> bool:
    """Return True if the stored OCPP URL is our endpoint (and not another OCPP server)."""
    return url is not None and OCPP_VIEW_BASE_PATH in url


async def async_release_charger(cloud: EaseeOcppCloud, serial: Serial) -> None:
    """Switch a charger whose subentry was removed back to cloud only.

    Otherwise it would keep trying to reach Home Assistant, which no longer accepts it,
    and nobody would answer its RFID requests.
    """
    try:
        connection = await cloud.read_connection(serial)
        if connection.is_enabled() and points_to_home_assistant(connection.url):
            await cloud.disable(serial)
            _LOGGER.info(
                "%s: OCPP subentry removed, charger switched back to cloud only", serial
            )
    except OcppCloudError as error:
        _LOGGER.warning(
            "%s: could not switch OCPP off after removal: %s", serial, error.reason
        )


async def async_release_removed_chargers(
    hass: HomeAssistant,
    entry: ConfigEntry,
    configured_serials: set[Serial],
    cloud: EaseeOcppCloud,
) -> None:
    """Compare with the chargers of the last setup and release the ones that disappeared."""
    store: Store[list[Serial]] = Store(hass, STORAGE_VERSION, STORAGE_KEY)
    previous_serials = set(await store.async_load() or [])
    for serial in previous_serials - configured_serials:
        entry.async_create_background_task(
            hass, async_release_charger(cloud, serial), f"easee_ocpp_release_{serial}"
        )
    await store.async_save(sorted(configured_serials))
    remove_entities_of_removed_chargers(hass, entry, configured_serials)
