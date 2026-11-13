"""End-to-end tests: a fake Easee charger against the OCPP view inside Home Assistant."""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator

from aiohttp import WSServerHandshakeError
from ocpp.v16 import call
import pytest

from custom_components.easee.ocpp import async_register_ocpp_view
from custom_components.easee.ocpp.hub import IdTagWhitelist, OcppChargerConfig, OcppHub
from custom_components.easee.ocpp.server import HUB_DATA_KEY
from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component

from .fake_charger import ClientConnection, FakeEaseeCharger, basic_auth, wait_until

SERIAL = "EHTEST01"
PASSWORD = "secret-password-123"
ALLOWED_CARD = "ABCD1234"


@pytest.fixture
async def hub(hass: HomeAssistant) -> AsyncIterator[OcppHub]:
    """Create a hub for one charger, registered like the integration does it."""
    await async_setup_component(hass, "http", {})
    async_register_ocpp_view(hass)
    ocpp_hub = OcppHub(
        hass, [OcppChargerConfig(SERIAL, PASSWORD)], IdTagWhitelist([ALLOWED_CARD])
    )
    await ocpp_hub.async_load()
    hass.data[HUB_DATA_KEY] = ocpp_hub
    yield ocpp_hub
    await ocpp_hub.async_shutdown()


@pytest.fixture
async def charger(hub: OcppHub, hass_client_no_auth) -> AsyncIterator[FakeEaseeCharger]:
    """Connect a fake charger whose message loop runs in the background."""
    client = await hass_client_no_auth()
    websocket = await client.ws_connect(
        f"/api/easee/ocpp/{SERIAL}",
        protocols=("ocpp1.6",),
        headers=basic_auth(SERIAL, PASSWORD),
    )
    fake = FakeEaseeCharger(SERIAL, ClientConnection(websocket))
    loop_task = asyncio.create_task(fake.start())
    yield fake
    loop_task.cancel()
    await asyncio.gather(loop_task, return_exceptions=True)
    await websocket.close()


@pytest.mark.parametrize("password", ["wrong", "p\u00e4sswort", "\U0001f511"])
async def test_wrong_password_is_refused(
    hub: OcppHub, hass_client_no_auth, password: str
) -> None:
    """A charger with a wrong password gets HTTP 401."""
    client = await hass_client_no_auth()
    with pytest.raises(WSServerHandshakeError) as refused:
        await client.ws_connect(
            f"/api/easee/ocpp/{SERIAL}",
            protocols=("ocpp1.6",),
            headers=basic_auth(SERIAL, password),
        )
    assert refused.value.status == 401


async def test_unknown_charger_is_refused(hub: OcppHub, hass_client_no_auth) -> None:
    """A serial without subentry gets HTTP 404."""
    client = await hass_client_no_auth()
    with pytest.raises(WSServerHandshakeError) as refused:
        await client.ws_connect(
            "/api/easee/ocpp/EHOTHER",
            protocols=("ocpp1.6",),
            headers=basic_auth("EHOTHER", PASSWORD),
        )
    assert refused.value.status == 404


async def test_bootstrap_configures_the_charger(
    hub: OcppHub, charger: FakeEaseeCharger
) -> None:
    """After connecting, measurands, interval, limit and triggers are set up."""
    await wait_until(lambda: len(charger.memory.triggered) == 2)

    assert hub.is_connected(SERIAL)
    assert (
        "Energy.Active.Import.Register"
        in charger.memory.configuration["MeterValuesSampledData"]
    )
    assert hub.state(SERIAL).meter_value_sample_interval == 30
    profile = charger.memory.charging_profiles[-1]
    assert profile["charging_profile_purpose"] == "ChargePointMaxProfile"
    assert profile["charging_schedule"]["charging_schedule_period"][0]["limit"] == 32.0
    assert hub.state(SERIAL).composite_limit_amps == 32.0
    assert "FreeCharging" in hub.state(SERIAL).unsupported_configuration_keys


async def test_whitelist_decides_authorization(
    hub: OcppHub, charger: FakeEaseeCharger
) -> None:
    """Known cards are accepted, unknown ones are invalid."""
    known = await charger.call(call.Authorize(id_tag=ALLOWED_CARD.lower()))
    unknown = await charger.call(call.Authorize(id_tag="DEADBEEF"))

    assert known.id_tag_info["status"] == "Accepted"
    assert unknown.id_tag_info["status"] == "Invalid"
    last_attempt = hub.state(SERIAL).last_authorization
    assert last_attempt is not None
    assert last_attempt.id_tag == "DEADBEEF"


async def test_transaction_and_meter_values(
    hub: OcppHub, charger: FakeEaseeCharger
) -> None:
    """A session tracks energy from the meter register."""
    await charger.boot()
    started = await charger.call(
        call.StartTransaction(
            connector_id=1,
            id_tag=ALLOWED_CARD,
            meter_start=1000,
            timestamp="2026-11-09T10:00:00Z",
        )
    )
    await charger.call(
        call.MeterValues(
            connector_id=1,
            meter_value=[
                {
                    "timestamp": "2026-11-09T10:05:00Z",
                    "sampledValue": [
                        {
                            "value": "1.5",
                            "measurand": "Energy.Active.Import.Register",
                            "unit": "kWh",
                        },
                        {
                            "value": "3.6",
                            "measurand": "Power.Active.Import",
                            "unit": "kW",
                        },
                        {
                            "value": "16.0",
                            "measurand": "Current.Import",
                            "phase": "L1",
                            "unit": "A",
                        },
                    ],
                }
            ],
        )
    )
    state = hub.state(SERIAL)
    assert state.session_energy_wh() == 500.0
    assert state.measurement("Power.Active.Import") == 3600.0
    assert state.measurement("Current.Import", "L1") == 16.0

    await charger.call(
        call.StopTransaction(
            meter_stop=1800,
            timestamp="2026-11-09T10:10:00Z",
            transaction_id=started.transaction_id,
        )
    )
    assert not state.has_transaction()
    assert state.session_energy_wh() == 800.0


async def test_disconnect_marks_charger_offline(
    hub: OcppHub, hass_client_no_auth, hass: HomeAssistant
) -> None:
    """Closing the websocket sets connected to False."""
    client = await hass_client_no_auth()
    websocket = await client.ws_connect(
        f"/api/easee/ocpp/{SERIAL}",
        protocols=("ocpp1.6",),
        headers=basic_auth(SERIAL, PASSWORD),
    )
    await wait_until(lambda: hub.is_connected(SERIAL))
    await websocket.close()
    await wait_until(lambda: not hub.is_connected(SERIAL))
    assert hub.state(SERIAL).connected is False
