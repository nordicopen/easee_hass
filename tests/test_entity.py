"""Tests for the Easee ChargerEntity base class and unit conversion helpers."""

import pytest

from custom_components.easee.controller import ProductData
from custom_components.easee.entity import (
    ChargerEntity,
    map_charger_status,
    map_phase_mode,
    map_pilot_mode,
    map_reason_no_current,
    round_0_dec,
    round_1_dec,
    round_2_dec,
)
from homeassistant.const import UnitOfEnergy, UnitOfPower


@pytest.mark.parametrize(
    "exc_cls",
    [AttributeError, KeyError, TypeError],
)
async def test_async_update_state_func_exception_resets_state_to_none(
    product_data: ProductData,
    exc_cls: type[Exception],
) -> None:
    """Ensure failing state_func resets _state to None instead of keeping raw key value."""
    product_data.state = {"chargerFirmware": 318}

    def failing_state_func(_state: dict) -> bool:
        raise exc_cls("missing dependent field")

    entity = ChargerEntity(
        data=product_data,
        name="failing_entity",
        state_key="state.chargerFirmware",
        units=None,
        convert_units_func=None,
        attrs_keys=[],
        device_class=None,
        state_func=failing_state_func,
    )
    # Pre-populate _state to verify stale values are cleared as well.
    entity._state = True

    await entity.async_update()

    assert entity._state is None


async def test_async_update_invalid_key_raises_index_error(
    product_data: ProductData,
) -> None:
    """Ensure an unknown state_key prefix without state_func raises IndexError."""
    product_data.state = {"chargerOpMode": 1}
    entity = ChargerEntity(
        data=product_data,
        name="invalid_key_entity",
        state_key="invalid.field",
        units=None,
        convert_units_func=None,
        attrs_keys=[],
        device_class=None,
    )

    with pytest.raises(IndexError, match="Wrong key for entity: invalid.field"):
        await entity.async_update()


@pytest.mark.parametrize(
    "unsupported_key",
    ["invalid.field", "site.costPerKWh"],
)
async def test_async_update_unsupported_state_func_key_raises_value_error(
    product_data: ProductData,
    unsupported_key: str,
) -> None:
    """Ensure an unsupported state_key prefix with state_func raises ValueError."""
    product_data.state = {"chargerOpMode": 1}
    entity = ChargerEntity(
        data=product_data,
        name="unsupported_state_func_entity",
        state_key=unsupported_key,
        units=None,
        convert_units_func=None,
        attrs_keys=[],
        device_class=None,
        state_func=lambda _data: True,
    )

    with pytest.raises(
        ValueError,
        match=f"Unsupported key for state_func: {unsupported_key}",
    ):
        await entity.async_update()


async def test_async_update_missing_key_skips_unit_conversion(
    product_data: ProductData,
) -> None:
    """Ensure missing keys evaluate to None without mapping None to 'unknown None'."""
    product_data.config = {}
    entity = ChargerEntity(
        data=product_data,
        name="phase_mode",
        state_key="config.phaseMode",
        units=None,
        convert_units_func=map_phase_mode,
        attrs_keys=[],
        device_class=None,
    )

    await entity.async_update()
    assert entity._state is None

    product_data.config = {"phaseMode": 2}
    await entity.async_update()
    assert entity._state == "auto"


async def test_async_update_state_func_with_unit_conversion(
    product_data: ProductData,
) -> None:
    """Ensure state_func output is passed through convert_units_func when not None."""
    product_data.config = {
        "circuitMaxCurrentP1": 15.6,
        "circuitMaxCurrentP2": 16.2,
        "circuitMaxCurrentP3": 15.8,
    }
    entity = ChargerEntity(
        data=product_data,
        name="max_circuit_limit",
        state_key="config.circuitMaxCurrentP1",
        units="A",
        convert_units_func=round_0_dec,
        attrs_keys=[],
        device_class=None,
        state_func=lambda config: float(
            max(
                config["circuitMaxCurrentP1"],
                config["circuitMaxCurrentP2"],
                config["circuitMaxCurrentP3"],
            )
        ),
    )

    await entity.async_update()
    assert entity._state == 16


def test_unit_conversion_helpers() -> None:
    """Test rounding and enum mapping helper functions."""
    assert round_0_dec(15.6) == 16
    assert round_1_dec(15.64) == 15.6
    assert round_2_dec(15.646) == 15.65
    assert round_0_dec(1.5, UnitOfPower.WATT) == 1500
    assert round_0_dec(2.25, UnitOfEnergy.WATT_HOUR) == 2250
    assert round_2_dec(None) is None

    assert map_charger_status(3) == "charging"
    assert map_charger_status(999) == "unknown 999"
    assert map_reason_no_current(0) == "ok"
    assert map_reason_no_current(999) == "unknown 999"
    assert map_phase_mode(1) == "single"
    assert map_phase_mode(3) == "three"
    assert map_pilot_mode("B") == "b"
    assert map_pilot_mode(None) is None
