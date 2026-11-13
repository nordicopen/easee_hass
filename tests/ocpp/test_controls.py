"""Numbers, switches, buttons, configuration entities and actions on a fake charger."""

from __future__ import annotations

from ocpp.v16 import call
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.easee.const import DOMAIN
from custom_components.easee.ocpp.const import CONF_ALLOWED_ID_TAGS
from custom_components.easee.ocpp.server import HUB_DATA_KEY
from homeassistant.const import ATTR_ENTITY_ID
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from .conftest import OCPP_SERIAL, ConnectCharger
from .fake_charger import FakeEaseeCharger, wait_until

UNKNOWN_CARD = "NEWCARD1"


def state_of(hass: HomeAssistant, entity_id: str) -> str:
    """State string of an entity that must exist."""
    state = hass.states.get(entity_id)
    assert state is not None, entity_id
    return state.state


def entity_id_of(hass: HomeAssistant, platform: str, key: str) -> str:
    """Entity id of an OCPP entity of the test charger."""
    entity_id = er.async_get(hass).async_get_entity_id(
        platform, DOMAIN, f"{OCPP_SERIAL}_ocpp_{key}"
    )
    assert entity_id is not None, f"{platform} {key} not registered"
    return entity_id


async def connected_charger(
    hass: HomeAssistant, connect_charger: ConnectCharger
) -> FakeEaseeCharger:
    """Connect and wait until the bootstrap is through."""
    charger = await connect_charger(OCPP_SERIAL)
    await wait_until(lambda: len(charger.memory.triggered) == 2)
    await hass.async_block_till_done()
    return charger


async def test_max_current_is_sent_and_kept(
    hass: HomeAssistant, connect_charger: ConnectCharger
) -> None:
    """Setting the number sends a ChargePointMaxProfile and survives as the limit for reconnects."""
    charger = await connected_charger(hass, connect_charger)
    number = entity_id_of(hass, "number", "max_current")

    await hass.services.async_call(
        "number", "set_value", {ATTR_ENTITY_ID: number, "value": 10}, blocking=True
    )

    assert (
        charger.memory.charging_profiles[-1]["charging_schedule"][
            "charging_schedule_period"
        ][0]["limit"]
        == 10
    )
    assert state_of(hass, number) == "10.0"
    assert hass.data[HUB_DATA_KEY].max_current(OCPP_SERIAL) == 10


async def test_configuration_keys_become_entities(
    hass: HomeAssistant, connect_charger: ConnectCharger
) -> None:
    """Every key read from the charger gets an entity of the matching type."""
    await connected_charger(hass, connect_charger)

    assert (
        state_of(hass, entity_id_of(hass, "switch", "config_LocalAuthorizeOffline"))
        == "on"
    )
    assert (
        hass.states.get(entity_id_of(hass, "number", "config_HeartbeatInterval"))
        is not None
    )
    assert (
        hass.states.get(entity_id_of(hass, "text", "config_MeterValuesSampledData"))
        is not None
    )
    read_only = er.async_get(hass).async_get(
        entity_id_of(hass, "sensor", "config_NumberOfConnectors")
    )
    assert read_only is not None
    assert read_only.disabled_by is not None


async def test_configuration_switch_writes_the_key(
    hass: HomeAssistant, connect_charger: ConnectCharger
) -> None:
    """Turning a configuration switch off sends ChangeConfiguration false."""
    charger = await connected_charger(hass, connect_charger)
    switch = entity_id_of(hass, "switch", "config_LocalAuthorizeOffline")

    await hass.services.async_call(
        "switch", "turn_off", {ATTR_ENTITY_ID: switch}, blocking=True
    )

    assert charger.memory.configuration["LocalAuthorizeOffline"] == "false"
    assert state_of(hass, switch) == "off"


async def test_charge_and_availability_switches(
    hass: HomeAssistant, connect_charger: ConnectCharger
) -> None:
    """Charge starts remotely with HA's own tag; availability sends ChangeAvailability."""
    charger = await connected_charger(hass, connect_charger)

    await hass.services.async_call(
        "switch",
        "turn_on",
        {ATTR_ENTITY_ID: entity_id_of(hass, "switch", "charge")},
        blocking=True,
    )
    await hass.services.async_call(
        "switch",
        "turn_off",
        {ATTR_ENTITY_ID: entity_id_of(hass, "switch", "available")},
        blocking=True,
    )

    assert (
        "RemoteStartTransaction",
        {"id_tag": "HOMEASSISTANT"},
    ) in charger.memory.commands
    assert ("ChangeAvailability", {"type": "Inoperative"}) in charger.memory.commands


async def test_learning_adds_the_next_unknown_card_without_reload(
    hass: HomeAssistant, loaded_entry: MockConfigEntry, connect_charger: ConnectCharger
) -> None:
    """After pressing learn, an unknown card is accepted and stored; the connection stays."""
    charger = await connected_charger(hass, connect_charger)
    hub_before = hass.data[HUB_DATA_KEY]
    before = await charger.call(call.Authorize(id_tag=UNKNOWN_CARD))

    await hass.services.async_call(
        "button",
        "press",
        {ATTR_ENTITY_ID: entity_id_of(hass, "button", "learn_rfid")},
        blocking=True,
    )
    learned = await charger.call(call.Authorize(id_tag=UNKNOWN_CARD))
    await hass.async_block_till_done()

    assert before.id_tag_info["status"] == "Invalid"
    assert learned.id_tag_info["status"] == "Accepted"
    assert UNKNOWN_CARD in loaded_entry.options[CONF_ALLOWED_ID_TAGS]
    assert hass.data[HUB_DATA_KEY] is hub_before
    again = await charger.call(call.Authorize(id_tag=UNKNOWN_CARD))
    assert again.id_tag_info["status"] == "Accepted"


async def test_buttons_send_their_commands(
    hass: HomeAssistant, connect_charger: ConnectCharger
) -> None:
    """Restart and unlock reach the charger."""
    charger = await connected_charger(hass, connect_charger)

    for key in ("soft_reset", "unlock"):
        await hass.services.async_call(
            "button",
            "press",
            {ATTR_ENTITY_ID: entity_id_of(hass, "button", key)},
            blocking=True,
        )

    assert ("Reset", {"type": "Soft"}) in charger.memory.commands
    assert ("UnlockConnector", {}) in charger.memory.commands


async def test_actions(hass: HomeAssistant, connect_charger: ConnectCharger) -> None:
    """The OCPP actions reach the charger and return its answers."""
    charger = await connected_charger(hass, connect_charger)
    registry_entry = er.async_get(hass).async_get(
        entity_id_of(hass, "number", "max_current")
    )
    assert registry_entry is not None
    target = {"device_id": registry_entry.device_id}

    configuration = await hass.services.async_call(
        DOMAIN,
        "ocpp_get_configuration",
        {**target, "key": "HeartbeatInterval"},
        blocking=True,
        return_response=True,
    )
    await hass.services.async_call(
        DOMAIN,
        "ocpp_send_local_list",
        {**target, "id_tags": ["A1"], "version": 3},
        blocking=True,
    )
    version = await hass.services.async_call(
        DOMAIN,
        "ocpp_get_local_list_version",
        target,
        blocking=True,
        return_response=True,
    )
    await hass.services.async_call(
        DOMAIN,
        "ocpp_clear_charging_profile",
        {**target, "purpose": "TxDefaultProfile"},
        blocking=True,
    )

    assert configuration is not None
    assert configuration["configuration"] == {
        "HeartbeatInterval": {"value": "86400", "readonly": False}
    }
    assert version == {"version": 3}
    assert (
        "ClearChargingProfile",
        {"charging_profile_purpose": "TxDefaultProfile"},
    ) in charger.memory.commands


async def test_temporary_limit_by_serial(
    hass: HomeAssistant, connect_charger: ConnectCharger
) -> None:
    """External controllers set an expiring limit above the max current profile."""
    charger = await connected_charger(hass, connect_charger)

    await hass.services.async_call(
        DOMAIN,
        "ocpp_set_current_limit",
        {"serial": OCPP_SERIAL, "current": 8, "duration": 120},
        blocking=True,
    )

    profile = charger.memory.charging_profiles[-1]
    assert profile["stack_level"] == 1
    assert profile["charging_profile_purpose"] == "ChargePointMaxProfile"
    assert profile["charging_schedule"]["duration"] == 130
    assert profile["charging_schedule"]["charging_schedule_period"][0]["limit"] == 8
