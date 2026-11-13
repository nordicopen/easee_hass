"""OCPP part of the integration diagnostics; passwords and RFID cards are redacted."""

from __future__ import annotations

from dataclasses import asdict
from typing import Any

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from .const import CONF_ALLOWED_ID_TAGS, CONF_OCPP_PASSWORD, SUBENTRY_TYPE_OCPP_CHARGER
from .hub import OcppHub
from .models import ChargePointState
from .server import HUB_DATA_KEY

TO_REDACT = {CONF_OCPP_PASSWORD, CONF_ALLOWED_ID_TAGS, "id_tag"}


def state_diagnostics(state: ChargePointState) -> dict[str, Any]:
    """Return the live state as plain data."""
    data = asdict(state)
    data["measurements"] = {
        f"{measurand}/{phase or '-'}": {
            "value": sample.value,
            "timestamp": sample.timestamp.isoformat(),
        }
        for (measurand, phase), sample in state.measurements.items()
    }
    data["unsupported_configuration_keys"] = sorted(
        state.unsupported_configuration_keys
    )
    return data


def ocpp_diagnostics(hass: HomeAssistant, entry: ConfigEntry) -> dict[str, Any]:
    """Subentries and live state of every OCPP charger."""
    hub: OcppHub | None = hass.data.get(HUB_DATA_KEY)
    chargers = (
        {
            serial: {
                "connected": hub.is_connected(serial),
                "state": state_diagnostics(hub.state(serial)),
            }
            for serial in hub.serials()
        }
        if hub is not None
        else {}
    )
    subentries = [
        async_redact_data(dict(subentry.data), TO_REDACT)
        for subentry in entry.subentries.values()
        if subentry.subentry_type == SUBENTRY_TYPE_OCPP_CHARGER
    ]
    return async_redact_data(
        {"subentries": subentries, "chargers": chargers}, TO_REDACT
    )
