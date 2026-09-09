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
from ocpp.v16.enums import Action, DataTransferStatus, RegistrationStatus

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
            _LOGGER.warning("A charger manufactured by %s connected to Easee OCPP server, this is probably not as intended?", charge_point_vendor)
        else:
            self.serial   = kwargs.get("chargePointSerialNumber")
            self.model    = kwargs.get("chargePointModel")
            self.firmware = kwargs.get("firmwareVersion")

        return call_result.BootNotification(
            current_time=datetime.now(tz=UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
            interval=60,
            status=RegistrationStatus.accepted.value,
        )

    @on(Action.heartbeat)
    def on_heartbeat(self, **kwargs):
        """Handle a Heartbeat."""
        now = datetime.now(tz=UTC)
        _LOGGER.debug("%s Heartbeat", self.id)
        return call_result.Heartbeat(current_time=now.strftime("%Y-%m-%dT%H:%M:%SZ"))

    @on(Action.status_notification)
    def on_status_notification(self, connector_id, error_code, status, **kwargs):
        """Handle a status notification."""

        _LOGGER.debug("Status notification  %s %s %s", connector_id, error_code, status)

        return call_result.StatusNotification()

    @on(Action.firmware_status_notification)
    def on_firmware_status(self, status, **kwargs):
        """Handle firmware status notification."""
        _LOGGER.debug("Firmware status notification  %s", status)
        return call_result.FirmwareStatusNotification()

    @on(Action.diagnostics_status_notification)
    def on_diagnostics_status(self, status, **kwargs):
        """Handle diagnostics status notification."""
        _LOGGER.info("Diagnostics upload status: %s", status)
        return call_result.DiagnosticsStatusNotification()

    @on(Action.security_event_notification)
    def on_security_event(self, type, timestamp, **kwargs):
        """Handle security event notification."""
        _LOGGER.info(
            "Security event notification received: %s at %s [techinfo: ]",
            type,
            timestamp,
        )
        return call_result.SecurityEventNotification()

    @on(Action.authorize)
    def on_authorize(self, id_tag, **kwargs):
        """Handle an Authorization request."""
        _LOGGER.debug("Authorize notification  %s", id_tag)
        return call_result.Authorize()

    @on(Action.start_transaction)
    def on_start_transaction(self, connector_id, id_tag, meter_start, **kwargs):
        """Handle a Start Transaction request."""
        _LOGGER.debug("Start transaction notification  %s", id_tag)

    @on(Action.stop_transaction)
    def on_stop_transaction(self, meter_stop, timestamp, transaction_id, **kwargs):
        """Stop the current transaction (multi-connector)."""
        _LOGGER.debug("Stop transaction notification  %s", meter_stop)

    @on(Action.data_transfer)
    def on_data_transfer(self, vendor_id, **kwargs):
        """Handle a Data transfer request."""
        _LOGGER.debug("Data transfer received from %s: %s", self.id, kwargs)
        return call_result.DataTransfer(status=DataTransferStatus.accepted.value)


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
        _LOGGER.debug("Connection from %s", charger_id)
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
        _LOGGER.info("Easee OCPP server started. URL ws://%s:%s", self.host, self.port)

        return self
