"""Configure a charge point after it (re)connected."""

from __future__ import annotations

from collections.abc import Awaitable
import logging

from ocpp.v16.enums import MessageTrigger

from .charge_point import CommandFailedError, EaseeChargePoint
from .const import (
    CONNECTOR_ID_VEHICLE,
    EASEE_HIDDEN_CONFIGURATION_KEYS,
    METER_VALUE_SAMPLE_INTERVAL_CANDIDATES,
    METER_VALUES_SAMPLED_DATA,
)

_LOGGER = logging.getLogger(__name__)

KEY_METER_VALUES_SAMPLED_DATA = "MeterValuesSampledData"
KEY_METER_VALUE_SAMPLE_INTERVAL = "MeterValueSampleInterval"


class ChargePointBootstrapper:
    """Brings a freshly connected charger into the state Home Assistant needs.

    A charger that only re-opens its websocket (e.g. after HA restarted) sends no
    BootNotification, so the hub also runs this shortly after every connect.
    Every step is best effort: one failing key must not keep the others from working.
    """

    def __init__(self, charge_point: EaseeChargePoint, max_current_amps: float) -> None:
        """Bootstrap this charge point; max_current_amps is the limit HA wants in force."""
        self._charge_point = charge_point
        self._max_current_amps = max_current_amps

    @property
    def _serial(self) -> str:
        return self._charge_point.state.serial

    async def run(self) -> None:
        """Run all steps in order."""
        _LOGGER.info("%s: bootstrap started", self._serial)
        await self._configure_measurands()
        await self._negotiate_sample_interval()
        await self._read_configuration()
        await self._apply_max_current()
        await self._request_current_status()
        _LOGGER.info("%s: bootstrap finished", self._serial)

    async def refresh(self) -> None:
        """Re-read everything without changing the configuration."""
        await self._read_configuration()
        await self._best_effort(
            "GetCompositeSchedule", self._charge_point.read_composite_limit()
        )
        await self._request_current_status()

    async def _configure_measurands(self) -> None:
        await self._best_effort(
            "MeterValuesSampledData",
            self._charge_point.change_configuration(
                KEY_METER_VALUES_SAMPLED_DATA, METER_VALUES_SAMPLED_DATA
            ),
        )

    async def _negotiate_sample_interval(self) -> None:
        for seconds in METER_VALUE_SAMPLE_INTERVAL_CANDIDATES:
            try:
                await self._charge_point.change_configuration(
                    KEY_METER_VALUE_SAMPLE_INTERVAL, str(seconds)
                )
            except CommandFailedError:
                continue
            self._charge_point.state.meter_value_sample_interval = seconds
            _LOGGER.info("%s: MeterValueSampleInterval %s s", self._serial, seconds)
            return
        _LOGGER.warning(
            "%s accepts no MeterValueSampleInterval of %s",
            self._serial,
            METER_VALUE_SAMPLE_INTERVAL_CANDIDATES,
        )

    async def _read_configuration(self) -> None:
        await self._best_effort(
            "GetConfiguration", self._charge_point.read_configuration()
        )
        # Easee answers at most one key per request (GetConfigurationMaxKeys = 1).
        for hidden_key in EASEE_HIDDEN_CONFIGURATION_KEYS:
            await self._best_effort(
                f"GetConfiguration {hidden_key}",
                self._charge_point.read_configuration([hidden_key]),
            )

    async def _apply_max_current(self) -> None:
        await self._best_effort(
            "ChargePointMaxProfile",
            self._charge_point.set_charge_point_max_current(self._max_current_amps),
        )
        await self._best_effort(
            "GetCompositeSchedule", self._charge_point.read_composite_limit()
        )

    async def _request_current_status(self) -> None:
        await self._best_effort(
            "TriggerMessage StatusNotification",
            self._charge_point.trigger_message(
                MessageTrigger.status_notification, CONNECTOR_ID_VEHICLE
            ),
        )
        await self._best_effort(
            "TriggerMessage MeterValues",
            self._charge_point.trigger_message(MessageTrigger.meter_values),
        )

    async def _best_effort(self, step: str, command: Awaitable[object]) -> None:
        try:
            await command
        except CommandFailedError as error:
            _LOGGER.warning("%s: %s failed: %s", self._serial, step, error)
