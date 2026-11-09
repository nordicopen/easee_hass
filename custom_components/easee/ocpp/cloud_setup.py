"""Switching a charger to local OCPP (and back) through the Easee cloud."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
import logging
from typing import Any

from pyeasee import Easee
from pyeasee.exceptions import (
    BadRequestException,
    ForbiddenServiceException,
    NotFoundException,
    ServerFailureException,
)

from .models import Serial

_LOGGER = logging.getLogger(__name__)

MINIMUM_OCPP_FIRMWARE = 344
MODE_DUAL_PROTOCOL = "DualProtocol"
MODE_OCPP_OFF = "OcppOff"
OPERATOR_EASEE = "Easee"
PHASES = (1, 2, 3)

CONNECTION_DETAILS_PATH = "/local-ocpp/v1/connection-details/{serial}"
APPLY_CONNECTION_PATH = "/local-ocpp/v1/connections/chargers/{serial}"


class OcppCloudError(Exception):
    """The Easee cloud refused or failed to change the OCPP connection."""

    def __init__(self, reason: str) -> None:
        """Reason is a translation key of the config flow errors."""
        super().__init__(reason)
        self.reason = reason


@dataclass(frozen=True)
class OcppCloudConnection:
    """What the Easee cloud has stored for a charger."""

    mode: str | None
    url: str | None

    def is_enabled(self) -> bool:
        """Return True if the charger connects to an OCPP server."""
        return self.mode == MODE_DUAL_PROTOCOL


@dataclass(frozen=True)
class ChargerReadiness:
    """Preconditions for local OCPP, read from the cloud data of a charger."""

    firmware: int | None
    wifi_rssi: int | None
    operator_name: str | None
    dynamic_circuit_current: tuple[float | None, ...]
    circuit_max_current: tuple[float | None, ...]

    def firmware_supports_ocpp(self) -> bool:
        """Easee supports local OCPP from firmware 344 on."""
        return self.firmware is not None and self.firmware >= MINIMUM_OCPP_FIRMWARE

    def is_on_wifi(self) -> bool:
        """Easee recommends Wi-Fi; over cellular the charger cannot reach Home Assistant."""
        return self.wifi_rssi is not None and self.wifi_rssi != 0

    def operator_is_easee(self) -> bool:
        """Return True if the site has Easee as operator, which OCPP requires."""
        return self.operator_name in {None, OPERATOR_EASEE}

    def circuit_is_limited(self) -> bool:
        """Return True if a dynamic circuit limit below the maximum caps the OCPP limits."""
        return any(
            dynamic is not None and maximum is not None and dynamic < maximum
            for dynamic, maximum in zip(
                self.dynamic_circuit_current, self.circuit_max_current, strict=True
            )
        )

    def lowest_circuit_maximum(self) -> int | None:
        """Circuit fuse rating, used to lift a dynamic circuit limit."""
        maxima = [
            maximum for maximum in self.circuit_max_current if maximum is not None
        ]
        return int(min(maxima)) if maxima else None


def optional_number(value: Any) -> float | None:
    """Return the value as float, or None if missing."""
    return float(value) if isinstance(value, int | float) else None


def charger_readiness(
    state: Mapping[str, Any] | None, config: Mapping[str, Any] | None
) -> ChargerReadiness:
    """Read the preconditions from the cloud state and config of a charger."""
    state = state or {}
    config = config or {}
    firmware = state.get("chargerFirmware")
    wifi_rssi = state.get("wiFiRSSI")
    return ChargerReadiness(
        firmware=int(firmware) if isinstance(firmware, int | float) else None,
        wifi_rssi=int(wifi_rssi) if isinstance(wifi_rssi, int | float) else None,
        operator_name=state.get("operatorName"),
        dynamic_circuit_current=tuple(
            optional_number(state.get(f"dynamicCircuitCurrentP{phase}"))
            for phase in PHASES
        ),
        circuit_max_current=tuple(
            optional_number(config.get(f"circuitMaxCurrentP{phase}"))
            for phase in PHASES
        ),
    )


class EaseeOcppCloud:
    """Stores and applies the OCPP connection of a charger in the Easee cloud."""

    def __init__(self, easee: Easee) -> None:
        """Use the logged-in cloud client of the integration."""
        self._easee = easee

    async def read_connection(self, serial: Serial) -> OcppCloudConnection:
        """Return the stored connection (mode None if nothing is stored)."""
        try:
            response = await self._easee.get(
                CONNECTION_DETAILS_PATH.format(serial=serial)
            )
            details = await response.json()
        except NotFoundException:
            return OcppCloudConnection(mode=None, url=None)
        except (ForbiddenServiceException, ServerFailureException) as error:
            raise cloud_error(error) from error
        url = (details.get("websocketConnectionArgs") or {}).get("url")
        return OcppCloudConnection(mode=details.get("connectivityMode"), url=url)

    async def enable(self, serial: Serial, url: str, password: str) -> None:
        """Point the charger at url with basic auth (the charger appends /<serial>)."""
        await self._store_and_apply(
            serial,
            {
                "connectivityMode": MODE_DUAL_PROTOCOL,
                "websocketConnectionArgs": {"url": url},
                "basicAuthPassword": password,
            },
        )

    async def disable(self, serial: Serial) -> None:
        """Switch the charger back to cloud only."""
        await self._store_and_apply(serial, {"connectivityMode": MODE_OCPP_OFF})

    async def _store_and_apply(
        self, serial: Serial, connection: dict[str, Any]
    ) -> None:
        try:
            response = await self._easee.post(
                CONNECTION_DETAILS_PATH.format(serial=serial), json=connection
            )
            version = (await response.json())["version"]
            await self._easee.post(
                APPLY_CONNECTION_PATH.format(serial=serial), json={"version": version}
            )
        except (
            ForbiddenServiceException,
            BadRequestException,
            ServerFailureException,
            KeyError,
        ) as error:
            raise cloud_error(error) from error
        _LOGGER.info(
            "%s: OCPP connection set to %s", serial, connection["connectivityMode"]
        )


def cloud_error(error: Exception) -> OcppCloudError:
    """Translate a pyeasee error into a config flow error key."""
    if isinstance(error, ForbiddenServiceException):
        return OcppCloudError("ocpp_forbidden")
    if isinstance(error, BadRequestException):
        return OcppCloudError("ocpp_rejected")
    return OcppCloudError("cloud_unavailable")
