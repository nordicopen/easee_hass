"""Inbound OCPP endpoint on Home Assistant's own web server.

The chargers connect to ``ws://<home assistant>:8123/api/easee/ocpp/<serial>``.
Using HA's port means no extra port has to be opened or mapped. HA's own
authentication does not apply (the charger cannot send an HA token); instead every
charger authenticates with HTTP basic auth (user = serial, password from its subentry).
"""

from __future__ import annotations

import base64
import binascii
from dataclasses import dataclass
import logging
from typing import TYPE_CHECKING

from aiohttp import WSMsgType, hdrs, web

from homeassistant.components.http import KEY_HASS, HomeAssistantView

from .const import OCPP_SUBPROTOCOL, OCPP_VIEW_URL, WEBSOCKET_PING_INTERVAL

if TYPE_CHECKING:
    from .hub import OcppHub

_LOGGER = logging.getLogger(__name__)

HUB_DATA_KEY = "easee_ocpp_hub"


class ConnectionClosedError(Exception):
    """The charger closed the websocket."""


class OcppWebSocketResponse(web.WebSocketResponse):
    """Keep late packets from restarting heartbeats on a closed socket."""

    def _reset_heartbeat(self) -> None:
        # aiohttp 3.14.5 can schedule a heartbeat reset while its close handshake
        # is in progress. Guard the reset until aiohttp handles this itself.
        if not self.closed:
            super()._reset_heartbeat()


class AiohttpOcppConnection:
    """Adapts an aiohttp websocket to the recv/send interface of the ocpp library."""

    def __init__(self, websocket: web.WebSocketResponse) -> None:
        """Wrap the websocket."""
        self._websocket = websocket

    async def recv(self) -> str:
        """Return the next text frame, raise ConnectionClosedError when the socket ends."""
        message = await self._websocket.receive()
        if message.type is WSMsgType.TEXT:
            return str(message.data)
        raise ConnectionClosedError(f"websocket message type {message.type.name}")

    async def send(self, message: str) -> None:
        """Send one text frame."""
        await self._websocket.send_str(message)

    async def close(self) -> None:
        """Close the websocket (e.g. when a newer connection replaces it)."""
        await self._websocket.close()


@dataclass(frozen=True)
class BasicCredentials:
    """Login and password from an HTTP basic auth header."""

    login: str
    password: str


def basic_credentials_from(request: web.Request) -> BasicCredentials | None:
    """Return the basic auth credentials of the request, or None if absent or malformed."""
    scheme, _, encoded = request.headers.get(hdrs.AUTHORIZATION, "").partition(" ")
    if scheme.lower() != "basic":
        return None
    try:
        decoded = base64.b64decode(encoded, validate=True).decode("utf-8")
    except (binascii.Error, UnicodeDecodeError):
        return None
    login, separator, password = decoded.partition(":")
    return BasicCredentials(login, password) if separator else None


def current_hub(request: web.Request) -> OcppHub | None:
    """Return the hub of the loaded config entry (None while the integration is unloaded)."""
    hass = request.app[KEY_HASS]
    hub: OcppHub | None = hass.data.get(HUB_DATA_KEY)
    return hub


class OcppWebSocketView(HomeAssistantView):
    """Accepts OCPP websocket connections from Easee chargers."""

    url = OCPP_VIEW_URL
    name = "api:easee:ocpp"
    requires_auth = False

    async def get(self, request: web.Request, serial: str) -> web.StreamResponse:
        """Authenticate the charger, then hand the websocket to the hub."""
        hub = current_hub(request)
        if hub is None or not hub.knows(serial):
            _LOGGER.warning("OCPP connection from unknown charger %s refused", serial)
            return web.Response(status=404)
        if not hub.password_matches(serial, basic_credentials_from(request)):
            hub.record_authentication_failure(serial)
            return web.Response(
                status=401, headers={"WWW-Authenticate": 'Basic realm="easee-ocpp"'}
            )

        websocket = OcppWebSocketResponse(
            protocols=(OCPP_SUBPROTOCOL,),
            heartbeat=WEBSOCKET_PING_INTERVAL.total_seconds(),
        )
        await websocket.prepare(request)
        if websocket.ws_protocol != OCPP_SUBPROTOCOL:
            _LOGGER.warning(
                "%s offered no %s subprotocol, closing", serial, OCPP_SUBPROTOCOL
            )
            await websocket.close()
            return websocket

        await hub.async_serve(serial, AiohttpOcppConnection(websocket))
        return websocket
