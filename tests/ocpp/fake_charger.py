"""A simulated Easee charger that talks OCPP 1.6J to the central system under test."""

from __future__ import annotations

import asyncio
import base64
from dataclasses import dataclass, field
import json
from typing import Any

from aiohttp import ClientWebSocketResponse, WSMsgType
from ocpp.routing import on
from ocpp.v16 import ChargePoint, call, call_result
from ocpp.v16.enums import Action

# Easee rejected every interval below 30 s in practice; the fake mimics that.
SMALLEST_ACCEPTED_SAMPLE_INTERVAL = 30
EASEE_UNKNOWN_KEYS = {"FreeCharging", "FreeChargingIdTag"}


class ClientConnection:
    """recv/send adapter for an aiohttp client websocket."""

    def __init__(self, websocket: ClientWebSocketResponse) -> None:
        """Wrap the websocket."""
        self._websocket = websocket

    async def recv(self) -> str:
        """Return the next text frame."""
        message = await self._websocket.receive()
        if message.type is not WSMsgType.TEXT:
            raise ConnectionError(message.type.name)
        return str(message.data)

    async def send(self, message: str) -> None:
        """Send a text frame."""
        await self._websocket.send_str(message)


@dataclass
class FakeChargerMemory:
    """What the central system did to the fake charger."""

    configuration: dict[str, str] = field(
        default_factory=lambda: {
            "MeterValueSampleInterval": "0",
            "HeartbeatInterval": "86400",
            "LocalAuthorizeOffline": "True",
            "MeterValuesSampledData": "Energy.Active.Import.Register",
        }
    )
    read_only_configuration: dict[str, str] = field(
        default_factory=lambda: {"NumberOfConnectors": "1"}
    )
    charging_profiles: list[dict[str, Any]] = field(default_factory=list)
    triggered: list[str] = field(default_factory=list)
    commands: list[tuple[str, dict[str, Any]]] = field(default_factory=list)


class FakeEaseeCharger(ChargePoint):
    """Answers the calls the central system sends, the way Easee does."""

    def __init__(self, serial: str, connection: ClientConnection) -> None:
        """Create the fake for one serial."""
        super().__init__(serial, connection, response_timeout=5)
        self.memory = FakeChargerMemory()

    @on(Action.change_configuration)
    def on_change_configuration(
        self, key: str, value: str, **kwargs: Any
    ) -> call_result.ChangeConfiguration:
        """Reject short sample intervals like a real Easee."""
        too_short = (
            key == "MeterValueSampleInterval"
            and int(value) < SMALLEST_ACCEPTED_SAMPLE_INTERVAL
        )
        if too_short:
            return call_result.ChangeConfiguration(status="Rejected")
        self.memory.configuration[key] = value
        return call_result.ChangeConfiguration(status="Accepted")

    @on(Action.get_configuration)
    def on_get_configuration(
        self, key: list[str] | None = None, **kwargs: Any
    ) -> call_result.GetConfiguration:
        """Return all keys, or the requested ones; Easee hides FreeCharging."""
        all_values = {
            **self.memory.configuration,
            **self.memory.read_only_configuration,
        }
        requested = key or list(all_values)
        known = [name for name in requested if name in all_values]
        unknown = [name for name in requested if name not in all_values]
        return call_result.GetConfiguration(
            configuration_key=[
                {
                    "key": name,
                    "readonly": name in self.memory.read_only_configuration,
                    "value": all_values[name],
                }
                for name in known
            ],
            unknown_key=unknown or None,
        )

    @on(Action.set_charging_profile)
    def on_set_charging_profile(
        self, connector_id: int, cs_charging_profiles: dict[str, Any], **kwargs: Any
    ) -> call_result.SetChargingProfile:
        """Remember the profile."""
        self.memory.charging_profiles.append(cs_charging_profiles)
        return call_result.SetChargingProfile(status="Accepted")

    @on(Action.get_composite_schedule)
    def on_get_composite_schedule(
        self, connector_id: int, duration: int, **kwargs: Any
    ) -> call_result.GetCompositeSchedule:
        """Report the limit of the last profile."""
        if not self.memory.charging_profiles:
            return call_result.GetCompositeSchedule(status="Rejected")
        schedule = without_decimals(
            self.memory.charging_profiles[-1]["charging_schedule"]
        )
        return call_result.GetCompositeSchedule(
            status="Accepted", connector_id=connector_id, charging_schedule=schedule
        )

    @on(Action.trigger_message)
    def on_trigger_message(
        self, requested_message: str, **kwargs: Any
    ) -> call_result.TriggerMessage:
        """Accept every trigger."""
        self.memory.triggered.append(requested_message)
        return call_result.TriggerMessage(status="Accepted")

    def _remember(self, action: str, **payload: Any) -> None:
        self.memory.commands.append((action, payload))

    @on(Action.change_availability)
    def on_change_availability(
        self, connector_id: int, type: str, **kwargs: Any
    ) -> call_result.ChangeAvailability:
        """Accept."""
        self._remember("ChangeAvailability", type=type)
        return call_result.ChangeAvailability(status="Accepted")

    @on(Action.remote_start_transaction)
    def on_remote_start(
        self, id_tag: str, **kwargs: Any
    ) -> call_result.RemoteStartTransaction:
        """Accept."""
        self._remember("RemoteStartTransaction", id_tag=id_tag)
        return call_result.RemoteStartTransaction(status="Accepted")

    @on(Action.reset)
    def on_reset(self, type: str, **kwargs: Any) -> call_result.Reset:
        """Accept."""
        self._remember("Reset", type=type)
        return call_result.Reset(status="Accepted")

    @on(Action.unlock_connector)
    def on_unlock(
        self, connector_id: int, **kwargs: Any
    ) -> call_result.UnlockConnector:
        """Unlock."""
        self._remember("UnlockConnector")
        return call_result.UnlockConnector(status="Unlocked")

    @on(Action.clear_charging_profile)
    def on_clear_profile(self, **kwargs: Any) -> call_result.ClearChargingProfile:
        """Forget all profiles."""
        self._remember("ClearChargingProfile", **kwargs)
        self.memory.charging_profiles.clear()
        return call_result.ClearChargingProfile(status="Accepted")

    @on(Action.send_local_list)
    def on_send_local_list(
        self, list_version: int, update_type: str, **kwargs: Any
    ) -> call_result.SendLocalList:
        """Accept."""
        self._remember("SendLocalList", list_version=list_version, **kwargs)
        return call_result.SendLocalList(status="Accepted")

    @on(Action.get_local_list_version)
    def on_get_local_list_version(
        self, **kwargs: Any
    ) -> call_result.GetLocalListVersion:
        """Version of the last list."""
        sent = [
            payload
            for action, payload in self.memory.commands
            if action == "SendLocalList"
        ]
        return call_result.GetLocalListVersion(
            list_version=sent[-1]["list_version"] if sent else 0
        )

    async def boot(self) -> call_result.BootNotification:
        """Send a BootNotification."""
        return await self.call(
            call.BootNotification(
                charge_point_model="Home",
                charge_point_vendor="Easee",
                firmware_version="344",
            )
        )


def without_decimals(payload: Any) -> Any:
    """Convert Decimals (parsed by the ocpp library) so the payload can be serialised again."""
    return json.loads(json.dumps(payload, default=float))


async def wait_until(condition: Any, timeout: float = 5.0) -> None:
    """Poll until condition() is truthy."""
    async with asyncio.timeout(timeout):
        while not condition():
            await asyncio.sleep(0.05)


def basic_auth(login: str, password: str) -> dict[str, str]:
    """Build the authorization header the way the Easee charger sends it."""
    token = base64.b64encode(f"{login}:{password}".encode()).decode()
    return {"Authorization": f"Basic {token}"}
