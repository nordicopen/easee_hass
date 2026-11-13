"""Regression coverage for malformed inputs, cloud failures and connection lifetimes."""

from __future__ import annotations

import asyncio
from datetime import timedelta
from typing import Any
from unittest.mock import AsyncMock, patch

from aiohttp import ClientConnectionError
from pyeasee.exceptions import AuthorizationFailedException, TooManyRequestsException
import pytest

from custom_components.easee.ocpp.address import suggested_ocpp_url, url_problem
from custom_components.easee.ocpp.bootstrap import ChargePointBootstrapper
from custom_components.easee.ocpp.charge_point import (
    CommandFailedError,
    EaseeChargePoint,
)
from custom_components.easee.ocpp.cloud_setup import EaseeOcppCloud, OcppCloudError
from custom_components.easee.ocpp.hub import IdTagWhitelist, OcppChargerConfig, OcppHub
from custom_components.easee.ocpp.meter_values import (
    parse_meter_values,
    parse_timestamp,
)
from custom_components.easee.ocpp.models import ChargePointState
from custom_components.easee.ocpp.server import ConnectionClosedError
from homeassistant.core import HomeAssistant

from .fake_charger import wait_until

SERIAL = "EHTEST01"
URL = "ws://192.168.1.10:8123/api/easee/ocpp"


@pytest.mark.parametrize(
    "url",
    [
        "ws://[broken/api/easee/ocpp",
        "ws://host:abc/api/easee/ocpp",
        "ws://host:65536/api/easee/ocpp",
        "ws://host:0/api/easee/ocpp",
        "ws://user:secret@host/api/easee/ocpp",
        URL + "?query=1",
        URL + "#fragment",
    ],
)
def test_malformed_url_is_rejected(url: str) -> None:
    """Bad URLs produce a validation error rather than a flow exception."""
    assert url_problem(url) == "invalid_url"


async def test_suggested_ipv6_url_is_bracketed(hass: HomeAssistant) -> None:
    """An IPv6 host needs brackets around its literal address."""
    with patch(
        "custom_components.easee.ocpp.address.get_url",
        return_value="http://[2001:db8::1]:8123",
    ):
        assert (
            await suggested_ocpp_url(hass) == "ws://[2001:db8::1]:8123/api/easee/ocpp"
        )


@pytest.mark.parametrize("value", ["NaN", "inf", "-inf", "1e400", "broken", None])
def test_invalid_meter_samples_do_not_replace_good_values(value: Any) -> None:
    """Invalid samples are ignored so sensors and diagnostics keep valid numbers."""
    measurements = parse_meter_values(
        [
            {
                "timestamp": "2026-11-13T10:00:00Z",
                "sampled_value": [
                    {"value": "12", "measurand": "Current.Import"},
                    {"value": value, "measurand": "Current.Import"},
                ],
            }
        ]
    )
    assert measurements[("Current.Import", None)].value == 12


def test_naive_timestamp_is_normalised_to_utc() -> None:
    """A charger timestamp without an offset must still allow duration calculations."""
    timestamp = parse_timestamp("2026-11-13T10:00:00")
    assert timestamp.utcoffset() == timedelta(0)


@pytest.mark.parametrize("operation", ["read_connection", "enable", "disable"])
@pytest.mark.parametrize(
    "error",
    [
        ClientConnectionError("unreachable"),
        TimeoutError(),
        ValueError("invalid JSON"),
        AuthorizationFailedException(),
        TooManyRequestsException(),
    ],
)
async def test_cloud_failures_become_flow_errors(
    operation: str, error: Exception
) -> None:
    """Expected transport and API failures stay within the flow's error handling."""
    client = AsyncMock()
    client.get.side_effect = client.post.side_effect = error
    cloud = EaseeOcppCloud(client)
    args = (SERIAL, URL, "password") if operation == "enable" else (SERIAL,)
    with pytest.raises(OcppCloudError, match="cloud_unavailable"):
        await getattr(cloud, operation)(*args)


async def test_bootstrap_failures_remain_in_diagnostics() -> None:
    """Failed steps stay visible, successful steps continue and recovery clears errors."""
    charge_point = AsyncMock(spec=EaseeChargePoint)
    charge_point.state = ChargePointState(SERIAL)
    charge_point.read_configuration.side_effect = CommandFailedError(
        "charger rejected request"
    )
    bootstrapper = ChargePointBootstrapper(charge_point, 16)
    await bootstrapper.run()
    assert "GetConfiguration" in charge_point.state.bootstrap_errors
    charge_point.set_charge_point_max_current.assert_awaited_once_with(16)

    charge_point.read_configuration.side_effect = None
    await bootstrapper.run()
    assert not charge_point.state.bootstrap_errors


class MemoryConnection:
    """Transport with a controllable close handshake for reconnect races."""

    def __init__(self) -> None:
        """Start connected, allowing close to finish immediately."""
        self.closed = asyncio.Event()
        self.closing = asyncio.Event()
        self.allow_close = asyncio.Event()
        self.allow_close.set()

    async def recv(self) -> str:
        """Wait until the transport is closed."""
        await self.closed.wait()
        raise ConnectionClosedError("test connection closed")

    async def send(self, message: str) -> None:
        """Accept outgoing messages."""

    async def close(self) -> None:
        """Let tests pause a replacement while another connection arrives."""
        self.closing.set()
        await self.allow_close.wait()
        self.closed.set()


async def test_simultaneous_reconnects_keep_only_one_connection(
    hass: HomeAssistant, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Two reconnects during a close handshake must not leave an orphan socket."""
    monkeypatch.setattr(
        "custom_components.easee.ocpp.hub.BOOTSTRAP_DELAY_AFTER_CONNECT",
        timedelta(days=1),
    )
    hub = OcppHub(hass, [OcppChargerConfig(SERIAL, "secret")], IdTagWhitelist([]))
    first, second, third = (MemoryConnection() for _ in range(3))
    tasks = [asyncio.create_task(hub.async_serve(SERIAL, first))]
    try:
        await wait_until(lambda: hub.is_connected(SERIAL))
        first.allow_close.clear()
        tasks.append(asyncio.create_task(hub.async_serve(SERIAL, second)))
        await first.closing.wait()
        tasks.append(asyncio.create_task(hub.async_serve(SERIAL, third)))
        await asyncio.sleep(0)
        first.allow_close.set()
        await wait_until(second.closed.is_set)
        assert not third.closed.is_set()
        assert hub.is_connected(SERIAL)
    finally:
        first.allow_close.set()
        await hub.async_shutdown()
        await asyncio.gather(*tasks)
    assert not hub.is_connected(SERIAL)


async def test_disconnect_cancels_bootstrap(hass: HomeAssistant) -> None:
    """Disconnecting cancels an in-flight bootstrap instead of waiting for timeouts."""
    hub = OcppHub(hass, [OcppChargerConfig(SERIAL, "secret")], IdTagWhitelist([]))
    connection = MemoryConnection()
    started = asyncio.Event()
    cancelled = asyncio.Event()

    async def bootstrap(self: Any) -> None:
        started.set()
        try:
            await asyncio.Future()
        finally:
            cancelled.set()

    with patch(
        "custom_components.easee.ocpp.hub.ChargePointBootstrapper.run", bootstrap
    ):
        task = asyncio.create_task(hub.async_serve(SERIAL, connection))
        try:
            await asyncio.wait_for(started.wait(), timeout=5)
            await connection.close()
            await asyncio.wait_for(task, timeout=5)
            assert cancelled.is_set()
            assert not hub.is_connected(SERIAL)
        finally:
            await hub.async_shutdown()
            await asyncio.gather(task, return_exceptions=True)
