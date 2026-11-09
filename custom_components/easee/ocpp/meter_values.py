"""Turn OCPP sampled values into normalised measurements."""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from datetime import datetime
import logging
from typing import Any

from homeassistant.util import dt as dt_util

from .models import Measurement, MeasurementKey

_LOGGER = logging.getLogger(__name__)

DEFAULT_MEASURAND = "Energy.Active.Import.Register"
# Easee reports per phase as "L1-N" etc.; HA entities only care about the line.
PHASE_ALIASES = {"L1-N": "L1", "L2-N": "L2", "L3-N": "L3"}
KILO_UNITS = {"kW", "kWh", "kvar", "kvarh", "kVA"}
# Only the measured value itself is relevant; begin/end of a transaction is context only.
IGNORED_CONTEXTS = {"Transaction.Begin"}


def parse_timestamp(text: str | None) -> datetime:
    """Parse an OCPP timestamp, falling back to now if missing or broken."""
    parsed = dt_util.parse_datetime(text) if text else None
    return parsed if parsed is not None else dt_util.utcnow()


def normalised_value(raw_value: str, unit: str | None) -> float:
    """Return the value in base units (W, Wh, A, V)."""
    value = float(raw_value)
    return value * 1000 if unit in KILO_UNITS else value


def measurement_key(sampled_value: Mapping[str, Any]) -> MeasurementKey:
    """Return the (measurand, phase) key of a sampled value."""
    measurand = sampled_value.get("measurand") or DEFAULT_MEASURAND
    raw_phase = sampled_value.get("phase")
    phase = PHASE_ALIASES.get(raw_phase, raw_phase) if raw_phase else None
    return measurand, phase


def parse_meter_values(
    meter_values: Iterable[Mapping[str, Any]],
) -> dict[MeasurementKey, Measurement]:
    """Return the measurements of a MeterValues message, keyed by measurand and phase."""
    measurements: dict[MeasurementKey, Measurement] = {}
    for meter_value in meter_values:
        timestamp = parse_timestamp(meter_value.get("timestamp"))
        for sampled_value in meter_value.get("sampled_value", []):
            if sampled_value.get("context") in IGNORED_CONTEXTS:
                continue
            try:
                value = normalised_value(
                    sampled_value["value"], sampled_value.get("unit")
                )
            except (KeyError, ValueError):
                _LOGGER.debug("Ignoring unparsable sampled value %s", sampled_value)
                continue
            measurements[measurement_key(sampled_value)] = Measurement(value, timestamp)
    return measurements
