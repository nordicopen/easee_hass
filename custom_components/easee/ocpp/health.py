"""Raises repair issues when an OCPP charger needs attention.

- the charger has not been connected for a while,
- it keeps failing basic auth (its stored password differs from the subentry),
- the configured address no longer points at this Home Assistant (e.g. new IP).
Each issue offers the same fix: apply the connection to the charger again via the cloud.
"""

from __future__ import annotations

from datetime import datetime, timedelta
import logging
import socket
from urllib.parse import urlsplit

from homeassistant.components.network import async_get_enabled_source_ips
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers import issue_registry as ir
from homeassistant.helpers.event import async_track_time_interval

from ..const import DOMAIN
from .const import CONF_OCPP_URL, CONF_SERIAL, SUBENTRY_TYPE_OCPP_CHARGER
from .hub import OcppHub
from .models import Serial

_LOGGER = logging.getLogger(__name__)

CHECK_INTERVAL = timedelta(minutes=1)
# A charger needed about five minutes after a cloud change; give it some extra time.
DISCONNECTED_ISSUE_AFTER = timedelta(minutes=15)
AUTHENTICATION_FAILURES_FOR_ISSUE = 3

ISSUE_DISCONNECTED = "ocpp_disconnected"
ISSUE_AUTHENTICATION_FAILED = "ocpp_authentication_failed"
ISSUE_ADDRESS_CHANGED = "ocpp_address_changed"
ALL_ISSUES = (ISSUE_DISCONNECTED, ISSUE_AUTHENTICATION_FAILED, ISSUE_ADDRESS_CHANGED)


def issue_id(kind: str, serial: Serial) -> str:
    """One issue per kind and charger."""
    return f"{kind}_{serial}"


def configured_urls(entry: ConfigEntry) -> dict[Serial, str]:
    """Return the address each charger was pointed at (older subentries may lack one)."""
    return {
        subentry.data[CONF_SERIAL]: subentry.data[CONF_OCPP_URL]
        for subentry in entry.subentries.values()
        if subentry.subentry_type == SUBENTRY_TYPE_OCPP_CHARGER
        and CONF_OCPP_URL in subentry.data
    }


async def async_host_addresses(hass: HomeAssistant, host: str) -> set[str]:
    """IP addresses a host name resolves to (empty if it does not resolve)."""
    try:
        results = await hass.loop.getaddrinfo(host, None, type=socket.SOCK_STREAM)
    except OSError:
        return set()
    return {str(result[4][0]) for result in results}


class OcppHealthMonitor:
    """Checks every charger once a minute and creates or deletes repair issues."""

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry, hub: OcppHub) -> None:
        """Watch the chargers of this hub."""
        self._hass = hass
        self._entry = entry
        self._hub = hub

    async def async_start(self) -> None:
        """Check the addresses once and the connections periodically."""
        for kind in ALL_ISSUES:
            self._remove_issues_of_removed_chargers(kind)
        await self._check_addresses()
        self._entry.async_on_unload(
            async_track_time_interval(
                self._hass, self._check_connections, CHECK_INTERVAL
            )
        )

    async def _check_connections(self, now: datetime) -> None:
        for serial in self._hub.serials():
            state = self._hub.state(serial)
            self._set_issue(
                ISSUE_DISCONNECTED,
                serial,
                state.disconnected_longer_than(DISCONNECTED_ISSUE_AFTER, now),
            )
            too_many_failures = (
                state.authentication_failures >= AUTHENTICATION_FAILURES_FOR_ISSUE
            )
            self._set_issue(ISSUE_AUTHENTICATION_FAILED, serial, too_many_failures)

    async def _check_addresses(self) -> None:
        own_addresses = {
            str(address) for address in await async_get_enabled_source_ips(self._hass)
        }
        for serial, url in configured_urls(self._entry).items():
            host = urlsplit(url).hostname or ""
            points_elsewhere = not (
                await async_host_addresses(self._hass, host) & own_addresses
            )
            self._set_issue(ISSUE_ADDRESS_CHANGED, serial, points_elsewhere, url=url)

    def _set_issue(
        self, kind: str, serial: Serial, present: bool, url: str = ""
    ) -> None:
        if not present:
            ir.async_delete_issue(self._hass, DOMAIN, issue_id(kind, serial))
            return
        ir.async_create_issue(
            self._hass,
            DOMAIN,
            issue_id(kind, serial),
            is_fixable=True,
            severity=ir.IssueSeverity.WARNING,
            translation_key=kind,
            translation_placeholders={"serial": serial, "url": url},
            data={"serial": serial},
        )

    def _remove_issues_of_removed_chargers(self, kind: str) -> None:
        configured = set(self._hub.serials())
        registry = ir.async_get(self._hass)
        for domain, existing_id in list(registry.issues):
            serial = existing_id.removeprefix(f"{kind}_")
            if (
                domain == DOMAIN
                and existing_id.startswith(f"{kind}_")
                and serial not in configured
            ):
                ir.async_delete_issue(self._hass, DOMAIN, existing_id)


def is_ocpp_issue(issue: str) -> bool:
    """Return True for issues this module creates."""
    return any(issue.startswith(f"{kind}_") for kind in ALL_ISSUES)
