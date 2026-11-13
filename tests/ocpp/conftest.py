"""Fixtures: the whole integration with a fake cloud and fake chargers."""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator, Callable, Coroutine
from contextlib import suppress
from datetime import timedelta
from ipaddress import IPv4Address
from typing import Any

from aiohttp import ClientConnectionResetError, ClientWebSocketResponse
import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.easee.const import DOMAIN
from custom_components.easee.ocpp.const import (
    CONF_ALLOWED_ID_TAGS,
    CONF_OCPP_PASSWORD,
    CONF_OCPP_URL,
    CONF_SERIAL,
    SUBENTRY_TYPE_OCPP_CHARGER,
)
from homeassistant.config_entries import ConfigSubentryData
from homeassistant.core import HomeAssistant

from .fake_charger import ClientConnection, FakeEaseeCharger, basic_auth
from .fake_cloud import FakeCloudCharger, FakeController

OCPP_SERIAL = "EHTEST01"
CLOUD_ONLY_SERIAL = "EHTEST02"
OCPP_PASSWORD = "secret-password-123"
HOME_ASSISTANT_IP = "192.168.1.10"
OCPP_URL = f"ws://{HOME_ASSISTANT_IP}:8123/api/easee/ocpp"
ALLOWED_CARD = "ABCD1234"

type ConnectCharger = Callable[..., Coroutine[Any, Any, FakeEaseeCharger]]


@pytest.fixture(autouse=True)
def no_bootstrap_delay(monkeypatch: pytest.MonkeyPatch) -> None:
    """Bootstrap immediately instead of waiting for a BootNotification."""
    monkeypatch.setattr(
        "custom_components.easee.ocpp.hub.BOOTSTRAP_DELAY_AFTER_CONNECT", timedelta(0)
    )


@pytest.fixture(autouse=True)
def fast_waiting(monkeypatch: pytest.MonkeyPatch) -> None:
    """Make the wizard poll quickly and give up after a second instead of ten minutes."""
    monkeypatch.setattr(
        "custom_components.easee.ocpp.config_flow.CONNECT_POLL_INTERVAL",
        timedelta(milliseconds=20),
    )
    monkeypatch.setattr(
        "custom_components.easee.ocpp.config_flow.CONNECT_TIMEOUT", timedelta(seconds=1)
    )


@pytest.fixture(autouse=True)
def home_assistant_address(monkeypatch: pytest.MonkeyPatch) -> None:
    """Home Assistant's own IP, so the address check needs no real network."""

    async def own_addresses(hass: HomeAssistant) -> list[IPv4Address]:
        return [IPv4Address(HOME_ASSISTANT_IP)]

    monkeypatch.setattr(
        "custom_components.easee.ocpp.health.async_get_enabled_source_ips",
        own_addresses,
    )


@pytest.fixture
def fake_cloud(monkeypatch: pytest.MonkeyPatch) -> type[FakeController]:
    """Replace the cloud controller; the account has two chargers."""
    FakeController.reset(
        [
            FakeCloudCharger(OCPP_SERIAL, "Garage"),
            FakeCloudCharger(CLOUD_ONLY_SERIAL, "Carport"),
        ]
    )
    monkeypatch.setattr("custom_components.easee.Controller", FakeController)
    return FakeController


@pytest.fixture
def config_entry(hass: HomeAssistant) -> MockConfigEntry:
    """Easee entry with one charger connected via OCPP."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        version=3,
        data={"username": "user@example.com", "password": "cloud-password"},
        options={"monitored_sites": ["Home"], CONF_ALLOWED_ID_TAGS: [ALLOWED_CARD]},
        subentries_data=[
            ConfigSubentryData(
                data={
                    CONF_SERIAL: OCPP_SERIAL,
                    CONF_OCPP_PASSWORD: OCPP_PASSWORD,
                    CONF_OCPP_URL: OCPP_URL,
                },
                subentry_type=SUBENTRY_TYPE_OCPP_CHARGER,
                title=f"OCPP Garage ({OCPP_SERIAL})",
                unique_id=OCPP_SERIAL,
            )
        ],
    )
    entry.add_to_hass(hass)
    return entry


@pytest.fixture
async def loaded_entry(
    hass: HomeAssistant, config_entry: MockConfigEntry, fake_cloud: type[FakeController]
) -> AsyncIterator[MockConfigEntry]:
    """Set up the integration."""
    assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()
    yield config_entry
    await hass.async_block_till_done()
    await hass.config_entries.async_unload(config_entry.entry_id)
    await hass.async_block_till_done()


@pytest.fixture
async def connect_charger(
    loaded_entry: MockConfigEntry, hass_client_no_auth
) -> AsyncIterator[ConnectCharger]:
    """Provide a factory that connects a fake charger and runs its message loop."""
    websockets: list[ClientWebSocketResponse] = []
    loops: list[asyncio.Task[None]] = []

    async def connect(serial: str, password: str = OCPP_PASSWORD) -> FakeEaseeCharger:
        client = await hass_client_no_auth()
        websocket = await client.ws_connect(
            f"/api/easee/ocpp/{serial}",
            protocols=("ocpp1.6",),
            headers=basic_auth(serial, password),
        )
        websockets.append(websocket)
        charger = FakeEaseeCharger(serial, ClientConnection(websocket))
        loops.append(asyncio.create_task(charger.start()))
        return charger

    yield connect
    for loop in loops:
        loop.cancel()
    # A replaced connection ends its loop with a connection error; that is expected here.
    await asyncio.gather(*loops, return_exceptions=True)
    for websocket in websockets:
        # The hub may already have closed a replaced connection.
        with suppress(ClientConnectionResetError):
            await websocket.close()
