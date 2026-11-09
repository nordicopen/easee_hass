"""The address under which a charger reaches Home Assistant's OCPP endpoint."""

from __future__ import annotations

from urllib.parse import urlsplit

from homeassistant.components.network import async_get_source_ip
from homeassistant.core import HomeAssistant
from homeassistant.helpers.network import NoURLAvailableError, get_url

from .const import OCPP_VIEW_BASE_PATH

DEFAULT_HA_PORT = 8123
SCHEME_PLAIN = "ws"
SCHEME_TLS = "wss"
MDNS_SUFFIX = ".local"


async def suggested_ocpp_url(hass: HomeAssistant) -> str:
    """Return the internal HA address as websocket URL, with mDNS names replaced by the IP."""
    try:
        internal = urlsplit(get_url(hass, allow_external=False, allow_cloud=False))
        host = internal.hostname
        port = internal.port or DEFAULT_HA_PORT
    except NoURLAvailableError:
        host, port = None, DEFAULT_HA_PORT
    if host is None or host.endswith(MDNS_SUFFIX):
        host = await async_get_source_ip(hass)
    return f"{SCHEME_PLAIN}://{host}:{port}{OCPP_VIEW_BASE_PATH}"


def url_problem(url: str) -> str | None:
    """Return a config flow error key if the charger could not use this URL."""
    parts = urlsplit(url.strip())
    if parts.scheme == SCHEME_TLS:
        # Easee only accepts certificates from a public CA; a self-signed HA certificate fails.
        return "wss_not_supported"
    if parts.scheme != SCHEME_PLAIN or not parts.hostname:
        return "invalid_url"
    if parts.hostname.endswith(MDNS_SUFFIX):
        return "mdns_host"
    if parts.path.rstrip("/") != OCPP_VIEW_BASE_PATH:
        return "wrong_path"
    return None


def normalised_url(url: str) -> str:
    """URL without trailing slash; the charger appends /<serial> itself."""
    return url.strip().rstrip("/")
