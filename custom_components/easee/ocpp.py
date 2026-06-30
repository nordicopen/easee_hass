"""Easee local OCPP server."""

from datetime import UTC, datetime
import logging

import websockets

from homeassistant.core import HomeAssistant
from ocpp.routing import on
from ocpp.v16 import (
    ChargePoint as cp,
    call as callv16,
    call_result,
    call_result as call_resultv16,
)
from ocpp.v16.enums import Action, RegistrationStatus

_LOGGER = logging.getLogger(__name__)


class OCPPCharger(cp):
    """Easee OCPP charger class."""

    def __init__(
        self,
        id,
        connection,
        hass: HomeAssistant,
    ):
        """Instantiate a ChargePoint."""
        super().__init__(id, connection, 10)

        self._call = callv16
        self._call_result = call_resultv16
        self._ocpp_version = "1.6"

        self.hass = hass

    @on(Action.boot_notification)
    def on_boot_notification(
        self, charge_point_vendor: str, charge_point_model: str, **kwargs
    ):
        """For every charger that sends boot notification."""

        _LOGGER.debug("Boot notification from %s %s %s", charge_point_vendor, charge_point_model, kwargs)
        if "Easee" not in charge_point_vendor:
            _LOGGER.warning("A charger manufactured by %s connected to Easee OCPP server, this is probably not correct?", charge_point_vendor)

        return call_result.BootNotification(
            current_time=datetime.now(UTC).isoformat(),
            interval=10,
            status=RegistrationStatus.accepted,
        )

    @on(Action.heartbeat)
    def on_heartbeat(self, **kwargs):
        """Handle a Heartbeat."""
        now = datetime.now(tz=UTC)
        return call_result.Heartbeat(current_time=now.strftime("%Y-%m-%dT%H:%M:%SZ"))

    @on(Action.status_notification)
    def on_status_notification(self, connector_id, error_code, status, **kwargs):
        """Handle a status notification."""

        _LOGGER.debug("Status notification  %s %s %s", connector_id, error_code, status)

        return call_result.StatusNotification()


class OCPPServer:
    """Easee OCPP server class."""

    async def on_connect(self, websocket):
        """For every new charge point that connects, creat a ChargePoint instance and start listening for messages."""
        try:
            requested_protocols = websocket.request.headers["Sec-WebSocket-Protocol"]
        except KeyError:
            _LOGGER.error("Client hasn't requested any Subprotocol. Closing Connection")
            return await websocket.close()
        if websocket.subprotocol:
            _LOGGER.debug("Protocols Matched: %s", websocket.subprotocol)
        else:
            # In the websockets lib if no subprotocols are supported by the
            # client and the server, it proceeds without a subprotocol,
            # so we have to manually close the connection.
            _LOGGER.warning(
                "Protocols Mismatched | Expected Subprotocols: %s,"
                " but client supports  %s | Closing connection",
                websocket.available_subprotocols,
                requested_protocols,
            )
            return await websocket.close()

        charger_id = websocket.request.path.strip("/")
        cp = OCPPCharger(charger_id, websocket, self.hass)

        try:
            await cp.start()
        except Exception as ex:
            _LOGGER.info(ex)

    async def start(self, hass: HomeAssistant, internal_address):
        """Start the OCPP server."""

        self.hass = hass
        self.ssl_context = None
        self.host = internal_address
        self.port = 9001

        server = await websockets.serve(
            self.on_connect,
            self.host,
            self.port,
            subprotocols=["ocpp1.6"],
            ssl=self.ssl_context,
        )
        self.server = server
        _LOGGER.debug("Easee OCPP server started. URL ws://%s:%s", self.host, self.port)

        return self
