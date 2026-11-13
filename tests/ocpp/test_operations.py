"""Repair issues, the repair fix flow, reconfiguring the address and diagnostics."""

from __future__ import annotations

import asyncio
from datetime import timedelta
from ipaddress import IPv4Address
from typing import Any
from unittest.mock import AsyncMock

from aiohttp import WSServerHandshakeError
import pytest
from pytest_homeassistant_custom_component.common import (
    MockConfigEntry,
    async_fire_time_changed,
)

from custom_components.easee.const import DOMAIN
from custom_components.easee.diagnostics import async_get_config_entry_diagnostics
from custom_components.easee.ocpp.const import (
    CONF_ALLOWED_ID_TAGS,
    CONF_OCPP_URL,
    SUBENTRY_TYPE_OCPP_CHARGER,
)
from custom_components.easee.ocpp.diagnostics import ocpp_diagnostics
from custom_components.easee.ocpp.health import (
    ISSUE_ADDRESS_CHANGED,
    ISSUE_AUTHENTICATION_FAILED,
    ISSUE_DISCONNECTED,
    issue_id,
)
from custom_components.easee.ocpp.repair_flow import ReapplyOcppConnectionFlow
from custom_components.easee.ocpp.server import HUB_DATA_KEY
from homeassistant.config_entries import SOURCE_RECONFIGURE
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.helpers import issue_registry as ir
from homeassistant.util import dt as dt_util

from .conftest import OCPP_PASSWORD, OCPP_SERIAL, OCPP_URL, ConnectCharger
from .fake_charger import basic_auth
from .fake_cloud import FakeController

NEW_URL = "ws://192.168.1.11:8123/api/easee/ocpp"


def has_issue(hass: HomeAssistant, kind: str) -> bool:
    """Return True if the repair issue exists for the test charger."""
    return (
        ir.async_get(hass).async_get_issue(DOMAIN, issue_id(kind, OCPP_SERIAL))
        is not None
    )


async def tick(hass: HomeAssistant) -> None:
    """Let the health monitor run once."""
    async_fire_time_changed(hass, dt_util.utcnow() + timedelta(minutes=1))
    await hass.async_block_till_done()


async def test_long_disconnect_raises_an_issue_that_clears_on_connect(
    hass: HomeAssistant, loaded_entry: MockConfigEntry, connect_charger: ConnectCharger
) -> None:
    """After 15 minutes offline there is an issue; it disappears once the charger is back."""
    hass.data[HUB_DATA_KEY].state(OCPP_SERIAL).disconnected_since = (
        dt_util.utcnow() - timedelta(minutes=20)
    )
    await tick(hass)
    assert has_issue(hass, ISSUE_DISCONNECTED)

    await connect_charger(OCPP_SERIAL)
    await tick(hass)
    assert not has_issue(hass, ISSUE_DISCONNECTED)


async def test_repeated_wrong_password_raises_an_issue(
    hass: HomeAssistant, loaded_entry: MockConfigEntry, hass_client_no_auth: Any
) -> None:
    """Three failed logins point the user at the fix."""
    client = await hass_client_no_auth()
    for _ in range(3):
        with pytest.raises(WSServerHandshakeError):
            await client.ws_connect(
                f"/api/easee/ocpp/{OCPP_SERIAL}",
                protocols=("ocpp1.6",),
                headers=basic_auth(OCPP_SERIAL, "wrong"),
            )
    await tick(hass)
    assert has_issue(hass, ISSUE_AUTHENTICATION_FAILED)


async def test_address_of_other_host_raises_an_issue(
    hass: HomeAssistant, loaded_entry: MockConfigEntry
) -> None:
    """A stored address that is not this Home Assistant is reported at setup."""
    assert not has_issue(hass, ISSUE_ADDRESS_CHANGED)
    subentry = next(iter(loaded_entry.subentries.values()))
    hass.config_entries.async_update_subentry(
        loaded_entry, subentry, data={**subentry.data, CONF_OCPP_URL: NEW_URL}
    )
    await hass.async_block_till_done()

    assert has_issue(hass, ISSUE_ADDRESS_CHANGED)


async def test_address_change_is_detected_without_a_reload(
    hass: HomeAssistant, loaded_entry: MockConfigEntry, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A changed HA network address is noticed by the periodic health check."""
    assert not has_issue(hass, ISSUE_ADDRESS_CHANGED)
    monkeypatch.setattr(
        "custom_components.easee.ocpp.health.async_get_enabled_source_ips",
        AsyncMock(return_value=[IPv4Address("192.168.1.11")]),
    )
    await tick(hass)
    assert has_issue(hass, ISSUE_ADDRESS_CHANGED)


async def test_fix_flow_applies_the_connection_again(
    hass: HomeAssistant, loaded_entry: MockConfigEntry
) -> None:
    """The fix sends address and stored password via the cloud and stores the address."""
    flow = ReapplyOcppConnectionFlow(OCPP_SERIAL)
    flow.hass = hass

    form = await flow.async_step_init()
    result = await flow.async_step_init({CONF_OCPP_URL: NEW_URL})

    assert form["type"] is FlowResultType.FORM
    assert result["type"] is FlowResultType.CREATE_ENTRY
    stored = FakeController.easee.stored[OCPP_SERIAL]
    assert stored["websocketConnectionArgs"]["url"] == NEW_URL
    assert stored["basicAuthPassword"] == OCPP_PASSWORD
    assert next(iter(loaded_entry.subentries.values())).data[CONF_OCPP_URL] == NEW_URL


async def test_reconfigure_changes_the_address_and_waits_for_the_new_connection(
    hass: HomeAssistant, loaded_entry: MockConfigEntry, connect_charger: ConnectCharger
) -> None:
    """Reconfiguring keeps the password and finishes once the charger reconnected."""
    await connect_charger(OCPP_SERIAL)

    def charger_reconnects(serial: str, details: dict[str, Any]) -> None:
        asyncio.get_running_loop().create_task(
            connect_charger(serial, details["basicAuthPassword"])
        )

    FakeController.easee.on_apply = charger_reconnects
    subentry_id = next(iter(loaded_entry.subentries))
    result: dict[str, Any] = dict(
        await hass.config_entries.subentries.async_init(
            (loaded_entry.entry_id, SUBENTRY_TYPE_OCPP_CHARGER),
            context={"source": SOURCE_RECONFIGURE, "subentry_id": subentry_id},
        )
    )
    assert result["step_id"] == "address"
    assert result["data_schema"]({})[CONF_OCPP_URL] == OCPP_URL

    result = dict(
        await hass.config_entries.subentries.async_configure(
            result["flow_id"], {CONF_OCPP_URL: NEW_URL}
        )
    )
    await hass.async_block_till_done(wait_background_tasks=True)
    result = dict(
        await hass.config_entries.subentries.async_configure(result["flow_id"])
    )
    if result["type"] is FlowResultType.SHOW_PROGRESS_DONE:
        result = dict(
            await hass.config_entries.subentries.async_configure(result["flow_id"])
        )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reconfigure_successful"
    assert loaded_entry.subentries[subentry_id].data[CONF_OCPP_URL] == NEW_URL
    assert (
        FakeController.easee.stored[OCPP_SERIAL]["basicAuthPassword"] == OCPP_PASSWORD
    )


async def test_diagnostics_hide_secrets(
    hass: HomeAssistant, loaded_entry: MockConfigEntry
) -> None:
    """Password and cards are redacted, the state is included."""
    diagnostics = ocpp_diagnostics(hass, loaded_entry)

    assert diagnostics["subentries"][0]["ocpp_password"] == "**REDACTED**"
    assert diagnostics["chargers"][OCPP_SERIAL]["connected"] is False


async def test_full_diagnostics_hide_the_rfid_whitelist(
    hass: HomeAssistant, loaded_entry: MockConfigEntry
) -> None:
    """Downloading integration diagnostics must not expose cards through options."""
    hass.data[DOMAIN]["diagnostics"] = []
    diagnostics = await async_get_config_entry_diagnostics(hass, loaded_entry)
    assert diagnostics["options"][CONF_ALLOWED_ID_TAGS] == "**REDACTED**"
