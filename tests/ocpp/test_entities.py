"""The OCPP entities inside Home Assistant, fed by a fake charger."""

from __future__ import annotations

from ocpp.v16 import call
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.easee.const import DOMAIN
from homeassistant.const import STATE_OFF, STATE_ON, STATE_UNAVAILABLE
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr, entity_registry as er

from .conftest import ALLOWED_CARD, CLOUD_ONLY_SERIAL, OCPP_SERIAL, ConnectCharger
from .fake_charger import wait_until


def entity_id_of(hass: HomeAssistant, platform: str, serial: str, key: str) -> str:
    """Look up the entity id by its unique id."""
    entity_id = er.async_get(hass).async_get_entity_id(
        platform, DOMAIN, f"{serial}_ocpp_{key}"
    )
    assert entity_id is not None, f"{platform} {key} of {serial} not registered"
    return entity_id


def state_of(hass: HomeAssistant, platform: str, key: str) -> str:
    """Return the state string of an OCPP entity of the test charger."""
    state = hass.states.get(entity_id_of(hass, platform, OCPP_SERIAL, key))
    assert state is not None
    return state.state


async def test_entities_only_for_chargers_with_subentry(
    hass: HomeAssistant, loaded_entry: MockConfigEntry
) -> None:
    """The cloud-only charger gets no OCPP entities; the OCPP charger's land on its existing device."""
    registry = er.async_get(hass)
    assert (
        registry.async_get_entity_id(
            "sensor", DOMAIN, f"{CLOUD_ONLY_SERIAL}_ocpp_power"
        )
        is None
    )

    power = registry.async_get(entity_id_of(hass, "sensor", OCPP_SERIAL, "power"))
    assert power is not None
    assert power.device_id is not None
    device = dr.async_get(hass).async_get(power.device_id)
    assert device is not None
    assert (DOMAIN, OCPP_SERIAL) in device.identifiers
    # HA 2026.11: a device belongs to one subentry; OCPP entities share the cloud device,
    # so they must not belong to the OCPP subentry or HA deletes one side's entities.
    assert power.config_subentry_id is None


async def test_removing_the_subentry_removes_the_ocpp_entities(
    hass: HomeAssistant, loaded_entry: MockConfigEntry
) -> None:
    """Without a subentry the OCPP entities of that charger are deleted."""
    power_entity_id = entity_id_of(hass, "sensor", OCPP_SERIAL, "power")
    subentry_id = next(iter(loaded_entry.subentries))

    assert hass.config_entries.async_remove_subentry(loaded_entry, subentry_id)
    await hass.async_block_till_done()

    assert er.async_get(hass).async_get(power_entity_id) is None


async def test_unavailable_until_connected(
    hass: HomeAssistant, loaded_entry: MockConfigEntry
) -> None:
    """Values are unavailable without connection, the connectivity sensor says off."""
    assert state_of(hass, "sensor", "power") == STATE_UNAVAILABLE
    assert state_of(hass, "binary_sensor", "connected") == STATE_OFF


async def test_states_follow_the_charger(
    hass: HomeAssistant, connect_charger: ConnectCharger
) -> None:
    """Status, measurements and session show up as entity states."""
    charger = await connect_charger(OCPP_SERIAL)
    await wait_until(lambda: state_of(hass, "binary_sensor", "connected") == STATE_ON)

    await charger.call(
        call.StatusNotification(connector_id=1, error_code="NoError", status="Charging")
    )
    await charger.call(
        call.StartTransaction(
            connector_id=1,
            id_tag=ALLOWED_CARD,
            meter_start=18_000_000,
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
                            "value": "18001.5",
                            "measurand": "Energy.Active.Import.Register",
                            "unit": "kWh",
                        },
                        {
                            "value": "11000",
                            "measurand": "Power.Active.Import",
                            "unit": "W",
                        },
                        {
                            "value": "231.2",
                            "measurand": "Voltage",
                            "phase": "L2-N",
                            "unit": "V",
                        },
                    ],
                }
            ],
        )
    )
    await wait_until(lambda: len(charger.memory.triggered) == 2)
    await hass.async_block_till_done()

    assert state_of(hass, "sensor", "status") == "charging"
    assert state_of(hass, "sensor", "power") == "11000.0"
    assert float(state_of(hass, "sensor", "energy")) == 18001.5
    assert float(state_of(hass, "sensor", "session_energy")) == 1.5
    assert state_of(hass, "sensor", "voltage_l2") == "231.2"
    assert state_of(hass, "sensor", "last_rfid_card") == ALLOWED_CARD
    assert state_of(hass, "binary_sensor", "transaction") == STATE_ON
    assert state_of(hass, "binary_sensor", "charging") == STATE_ON
    assert float(state_of(hass, "sensor", "charging_limit")) == 32.0
