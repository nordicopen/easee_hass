"""Tests for Easee entity definitions and state_func lambdas in const.py."""

from collections.abc import Callable
from typing import Any

from pyeasee import ChargerSchedule, ChargerWeeklySchedule
import pytest

from custom_components.easee.binary_sensor import ChargerBinarySensor
from custom_components.easee.const import (
    EASEE_EQ_ENTITIES,
    MANDATORY_EASEE_ENTITIES,
    OPTIONAL_EASEE_ENTITIES,
)
from custom_components.easee.controller import ENTITY_TYPES, ProductData
from custom_components.easee.entity import ChargerEntity, convert_units_funcs
from custom_components.easee.sensor import ChargerSensor
from custom_components.easee.switch import ChargerSwitch


@pytest.mark.parametrize(
    ("entity_id", "cfg"),
    [
        *[(f"mandatory.{k}", v) for k, v in MANDATORY_EASEE_ENTITIES.items()],
        *[(f"optional.{k}", v) for k, v in OPTIONAL_EASEE_ENTITIES.items()],
        *[(f"equalizer.{k}", v) for k, v in EASEE_EQ_ENTITIES.items()],
    ],
)
def test_entity_definitions_valid(entity_id: str, cfg: dict[str, Any]) -> None:
    """Ensure every entity definition has valid convert_units_func, type, and unique attrs."""
    convert_func_name = cfg.get("convert_units_func")
    assert convert_func_name is None or convert_func_name in convert_units_funcs, (
        f"{entity_id} has invalid convert_units_func={convert_func_name!r}"
    )

    entity_type = cfg.get("type")
    assert entity_type is None or entity_type in ENTITY_TYPES, (
        f"{entity_id} has unknown entity type={entity_type!r}"
    )

    attrs = cfg.get("attrs", [])
    assert len(attrs) == len(set(attrs)), (
        f"{entity_id} contains duplicate attribute keys: {attrs}"
    )


async def test_update_available_binary_sensor(
    product_data: ProductData,
    create_entity: Callable[[str], ChargerEntity],
) -> None:
    """Test update_available binary sensor across partial and complete firmware states."""
    sensor = create_entity("update_available")
    assert isinstance(sensor, ChargerBinarySensor)

    # Initial startup before state is polled
    product_data.state = None
    await sensor.async_update()
    assert sensor.is_on is None

    # chargerFirmware polled, but latestFirmware not yet in state dict
    product_data.state = {"chargerFirmware": 318}
    await sensor.async_update()
    assert sensor.is_on is None

    # latestFirmware polled, but chargerFirmware missing
    product_data.state = {"latestFirmware": 320}
    await sensor.async_update()
    assert sensor.is_on is None

    # Explicit None values (e.g. after firmware endpoint auth failure)
    product_data.state = {"chargerFirmware": 318, "latestFirmware": None}
    await sensor.async_update()
    assert sensor.is_on is None

    product_data.state = {"chargerFirmware": None, "latestFirmware": 320}
    await sensor.async_update()
    assert sensor.is_on is None

    # Newer firmware available
    product_data.state = {"chargerFirmware": 318, "latestFirmware": 320}
    await sensor.async_update()
    assert sensor.is_on is True

    # Firmware up to date
    product_data.state = {"chargerFirmware": 320, "latestFirmware": 320}
    await sensor.async_update()
    assert sensor.is_on is False


async def test_cable_locked_binary_sensor(
    product_data: ProductData,
    create_entity: Callable[[str], ChargerEntity],
) -> None:
    """Test cable_locked LOCK binary sensor (False=locked, True=unlocked, None=unknown)."""
    sensor = create_entity("cable_locked")
    assert isinstance(sensor, ChargerBinarySensor)

    product_data.state = None
    await sensor.async_update()
    assert sensor.is_on is None

    product_data.state = {}
    await sensor.async_update()
    assert sensor.is_on is None

    product_data.state = {"cableLocked": None}
    await sensor.async_update()
    assert sensor.is_on is None

    product_data.state = {"cableLocked": True}
    await sensor.async_update()
    assert sensor.is_on is False

    product_data.state = {"cableLocked": False}
    await sensor.async_update()
    assert sensor.is_on is True


async def test_basic_and_weekly_schedule_switches(
    product_data: ProductData,
    create_entity: Callable[[str], ChargerEntity],
) -> None:
    """Test basic_schedule and weekly_schedule switches with pyeasee BaseDict objects."""
    basic_switch = create_entity("basic_schedule")
    weekly_switch = create_entity("weekly_schedule")
    assert isinstance(basic_switch, ChargerSwitch)
    assert isinstance(weekly_switch, ChargerSwitch)

    # Uninitialized schedules default to False
    product_data.schedule = None
    product_data.weekly_schedule = None
    await basic_switch.async_update()
    await weekly_switch.async_update()
    assert basic_switch.is_on is False
    assert weekly_switch.is_on is False

    # Disabled pyeasee schedule mappings (BaseDict subclasses without .isEnabled attribute)
    product_data.schedule = ChargerSchedule({"isEnabled": False})
    product_data.weekly_schedule = ChargerWeeklySchedule({"isEnabled": False})
    await basic_switch.async_update()
    await weekly_switch.async_update()
    assert basic_switch.is_on is False
    assert weekly_switch.is_on is False

    # Enabled pyeasee schedule mappings
    product_data.schedule = ChargerSchedule({"isEnabled": True})
    product_data.weekly_schedule = ChargerWeeklySchedule(
        {"isEnabled": True, "days": []}
    )
    await basic_switch.async_update()
    await weekly_switch.async_update()
    assert basic_switch.is_on is True
    assert weekly_switch.is_on is True


async def test_current_sensor_and_cost_per_kwh_cleanup(
    product_data: ProductData,
    create_entity: Callable[[str], ChargerEntity],
) -> None:
    """Test current sensor configuration/calculation and cost_per_kwh unique attributes."""
    assert OPTIONAL_EASEE_ENTITIES["current"]["convert_units_func"] is None

    current_sensor = create_entity("current")
    assert isinstance(current_sensor, ChargerSensor)

    # Incomplete phase currents (None) must yield None via TypeError handling
    product_data.state = {
        "inCurrentT2": 10.0,
        "inCurrentT3": None,
        "inCurrentT4": 0.0,
        "inCurrentT5": 0.0,
    }
    await current_sensor.async_update()
    assert current_sensor.native_value is None

    product_data.state = {
        "inCurrentT2": 10.5,
        "inCurrentT3": 15.2,
        "inCurrentT4": 14.8,
        "inCurrentT5": 0.0,
    }
    await current_sensor.async_update()
    assert current_sensor.native_value == 15.2

    cost_sensor = create_entity("cost_per_kwh")
    assert isinstance(cost_sensor, ChargerSensor)
    assert OPTIONAL_EASEE_ENTITIES["cost_per_kwh"]["attrs"] == [
        "site.costPerKWh",
        "site.costPerKwhExcludeVat",
        "site.vat",
        "site.currencyId",
    ]
    assert product_data.observers["site"]["costPerKwhExcludeVat"] == [cost_sensor]
