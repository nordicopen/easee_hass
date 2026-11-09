"""The setup wizard that connects a charger via local OCPP."""

from __future__ import annotations

import asyncio
from typing import Any

import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.easee.ocpp.config_flow import CHECK_FAILED
from custom_components.easee.ocpp.const import (
    CONF_OCPP_PASSWORD,
    CONF_OCPP_URL,
    CONF_SERIAL,
    SUBENTRY_TYPE_OCPP_CHARGER,
)
from homeassistant.config_entries import SOURCE_USER
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from .conftest import CLOUD_ONLY_SERIAL, OCPP_SERIAL, ConnectCharger
from .fake_cloud import FakeController

HA_URL = "ws://192.168.1.10:8123/api/easee/ocpp"
type FlowResult = dict[str, Any]


async def start_flow(hass: HomeAssistant, entry: MockConfigEntry) -> FlowResult:
    """Open the wizard."""
    return dict(
        await hass.config_entries.subentries.async_init(
            (entry.entry_id, SUBENTRY_TYPE_OCPP_CHARGER),
            context={"source": SOURCE_USER},
        )
    )


async def submit(
    hass: HomeAssistant, result: FlowResult, user_input: dict[str, Any] | None = None
) -> FlowResult:
    """Submit one step."""
    return dict(
        await hass.config_entries.subentries.async_configure(
            result["flow_id"], user_input
        )
    )


async def until_address(hass: HomeAssistant, entry: MockConfigEntry) -> FlowResult:
    """Pick the cloud-only charger and pass the precondition step."""
    result = await start_flow(hass, entry)
    assert result["step_id"] == "user"
    result = await submit(hass, result, {CONF_SERIAL: CLOUD_ONLY_SERIAL})
    assert result["step_id"] == "prerequisites"
    return await submit(hass, result, {})


async def finish_progress(hass: HomeAssistant, result: FlowResult) -> FlowResult:
    """Let the connect task finish and follow the progress-done step."""
    assert result["type"] is FlowResultType.SHOW_PROGRESS
    await hass.async_block_till_done(wait_background_tasks=True)
    result = await submit(hass, result)
    # HA follows the progress-done step on its own once the task has finished.
    if result["type"] is FlowResultType.SHOW_PROGRESS_DONE:
        result = await submit(hass, result)
    return result


async def test_only_unconfigured_chargers_are_offered(
    hass: HomeAssistant, loaded_entry: MockConfigEntry
) -> None:
    """The charger that already has a subentry is not in the list."""
    result = await start_flow(hass, loaded_entry)
    selector = result["data_schema"].schema[CONF_SERIAL]
    offered = [option["value"] for option in selector.config["options"]]
    assert offered == [CLOUD_ONLY_SERIAL]


async def test_happy_path_switches_the_charger_and_waits_for_it(
    hass: HomeAssistant, loaded_entry: MockConfigEntry, connect_charger: ConnectCharger
) -> None:
    """The wizard stores the connection in the cloud, the charger connects, the subentry is created."""

    def charger_connects_after_apply(serial: str, details: dict[str, Any]) -> None:
        asyncio.get_running_loop().create_task(
            connect_charger(serial, details["basicAuthPassword"])
        )

    FakeController.easee.on_apply = charger_connects_after_apply
    result = await until_address(hass, loaded_entry)
    assert result["step_id"] == "address"

    result = await submit(hass, result, {CONF_OCPP_URL: HA_URL + "/"})
    result = await finish_progress(hass, result)

    assert result["type"] is FlowResultType.CREATE_ENTRY
    stored = FakeController.easee.stored[CLOUD_ONLY_SERIAL]
    assert stored["connectivityMode"] == "DualProtocol"
    assert stored["websocketConnectionArgs"]["url"] == HA_URL
    subentry = next(
        sub
        for sub in loaded_entry.subentries.values()
        if sub.unique_id == CLOUD_ONLY_SERIAL
    )
    assert subentry.data[CONF_OCPP_PASSWORD] == stored["basicAuthPassword"]
    assert len(subentry.data[CONF_OCPP_PASSWORD]) == 20
    assert subentry.data[CONF_OCPP_URL] == HA_URL


async def test_timeout_offers_rollback(
    hass: HomeAssistant, loaded_entry: MockConfigEntry
) -> None:
    """Without connection the user can switch the charger back to cloud only."""
    result = await until_address(hass, loaded_entry)
    result = await submit(hass, result, {CONF_OCPP_URL: HA_URL})
    result = await finish_progress(hass, result)
    assert result["type"] is FlowResultType.MENU
    assert result["step_id"] == "connection_failed"

    result = await submit(hass, result, {"next_step_id": "rollback"})

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "rolled_back"
    assert (
        FakeController.easee.stored[CLOUD_ONLY_SERIAL]["connectivityMode"] == "OcppOff"
    )


@pytest.mark.parametrize(
    ("url", "error"),
    [
        ("ws://homeassistant.local:8123/api/easee/ocpp", "mdns_host"),
        ("wss://192.168.1.10:8123/api/easee/ocpp", "wss_not_supported"),
        ("http://192.168.1.10:8123/api/easee/ocpp", "invalid_url"),
        ("ws://192.168.1.10:8123/ocpp", "wrong_path"),
    ],
)
async def test_unusable_addresses_are_rejected(
    hass: HomeAssistant, loaded_entry: MockConfigEntry, url: str, error: str
) -> None:
    """Addresses the charger could not use are explained instead of applied."""
    result = await until_address(hass, loaded_entry)
    result = await submit(hass, result, {CONF_OCPP_URL: url})
    assert result["step_id"] == "address"
    assert result["errors"] == {CONF_OCPP_URL: error}
    assert FakeController.easee.applied == []


async def test_cloud_refusal_returns_to_the_address_step(
    hass: HomeAssistant, loaded_entry: MockConfigEntry
) -> None:
    """A user without permission sees why instead of waiting ten minutes."""
    FakeController.easee.forbidden = True
    result = await until_address(hass, loaded_entry)
    result = await submit(hass, result, {CONF_OCPP_URL: HA_URL})
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "address"
    assert result["errors"] == {"base": "ocpp_forbidden"}


async def test_circuit_limit_can_be_lifted(
    hass: HomeAssistant, loaded_entry: MockConfigEntry
) -> None:
    """A dynamic circuit limit below the fuse is shown and can be lifted."""
    product = FakeController.product_data(CLOUD_ONLY_SERIAL)
    product.state["dynamicCircuitCurrentP1"] = 10
    result = await start_flow(hass, loaded_entry)
    result = await submit(hass, result, {CONF_SERIAL: CLOUD_ONLY_SERIAL})
    assert "reset_circuit_limit" in result["data_schema"].schema
    assert result["description_placeholders"]["circuit_check"] == CHECK_FAILED

    result = await submit(hass, result, {"reset_circuit_limit": True})

    assert result["step_id"] == "address"
    assert product.circuit.dynamic_current_requests == [32]


async def test_old_firmware_aborts(
    hass: HomeAssistant, loaded_entry: MockConfigEntry
) -> None:
    """Firmware below 344 cannot do local OCPP."""
    FakeController.product_data(CLOUD_ONLY_SERIAL).state["chargerFirmware"] = 300
    result = await start_flow(hass, loaded_entry)
    result = await submit(hass, result, {CONF_SERIAL: CLOUD_ONLY_SERIAL})
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "firmware_too_old"


async def test_removing_a_subentry_switches_the_charger_back(
    hass: HomeAssistant, loaded_entry: MockConfigEntry
) -> None:
    """After deletion the charger goes back to cloud only, if it pointed at Home Assistant."""
    FakeController.easee.stored[OCPP_SERIAL] = {
        "connectivityMode": "DualProtocol",
        "websocketConnectionArgs": {"url": f"{HA_URL}/{OCPP_SERIAL}"},
    }
    subentry_id = next(iter(loaded_entry.subentries))

    hass.config_entries.async_remove_subentry(loaded_entry, subentry_id)
    await hass.async_block_till_done(wait_background_tasks=True)

    assert FakeController.easee.stored[OCPP_SERIAL]["connectivityMode"] == "OcppOff"


async def test_removal_leaves_foreign_ocpp_servers_alone(
    hass: HomeAssistant, loaded_entry: MockConfigEntry
) -> None:
    """A charger the user pointed at another OCPP server is not touched."""
    foreign = {
        "connectivityMode": "DualProtocol",
        "websocketConnectionArgs": {"url": "ws://other:9000/ocpp"},
    }
    FakeController.easee.stored[OCPP_SERIAL] = foreign
    subentry_id = next(iter(loaded_entry.subentries))

    hass.config_entries.async_remove_subentry(loaded_entry, subentry_id)
    await hass.async_block_till_done(wait_background_tasks=True)

    assert FakeController.easee.stored[OCPP_SERIAL] is foreign
