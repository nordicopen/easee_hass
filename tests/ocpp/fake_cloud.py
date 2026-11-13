"""Stand-in for the Easee cloud, so the integration loads without network access."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

from pyeasee.exceptions import ForbiddenServiceException, NotFoundException

from custom_components.easee.const import DOMAIN
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr

type Serial = str
type ConnectionDetails = dict[str, Any]

FIRMWARE_WITH_OCPP = 360


@dataclass(frozen=True)
class FakeCloudCharger:
    """The few charger attributes the OCPP code reads from the cloud side."""

    id: str
    name: str


@dataclass
class FakeCircuit:
    """Records dynamic circuit limit changes."""

    dynamic_current_requests: list[int] = field(default_factory=list)

    async def set_dynamic_current(self, current_p1: int) -> None:
        """Remember the requested limit."""
        self.dynamic_current_requests.append(current_p1)


@dataclass
class FakeProductData:
    """Cloud state and config of one charger, as the controller keeps it."""

    product: FakeCloudCharger
    state: dict[str, Any]
    config: dict[str, Any]
    circuit: FakeCircuit


class FakeResponse:
    """aiohttp-like response with a JSON body."""

    def __init__(self, body: Any) -> None:
        """Hold the body."""
        self._body = body

    async def json(self) -> Any:
        """Return the body."""
        return self._body


class FakeEaseeApi:
    """The local-ocpp endpoints of the Easee cloud."""

    def __init__(self) -> None:
        """No charger has OCPP configured."""
        self.stored: dict[Serial, ConnectionDetails] = {}
        self.applied: list[tuple[Serial, ConnectionDetails]] = []
        self.forbidden = False
        self.on_apply: Callable[[Serial, ConnectionDetails], None] | None = None

    async def get(self, path: str) -> FakeResponse:
        """GET connection-details."""
        serial = path.rsplit("/", 1)[1]
        if serial not in self.stored:
            raise NotFoundException
        return FakeResponse(self.stored[serial])

    async def post(self, path: str, json: dict[str, Any]) -> FakeResponse:
        """POST connection-details (store) or connections/chargers (apply)."""
        if self.forbidden:
            raise ForbiddenServiceException({"title": "Forbidden"})
        serial = path.rsplit("/", 1)[1]
        if "connection-details" in path:
            self.stored[serial] = json
            return FakeResponse({"version": f"v{len(self.applied) + 1}"})
        details = self.stored[serial]
        self.applied.append((serial, details))
        if self.on_apply is not None:
            self.on_apply(serial, details)
        return FakeResponse({})


def ready_product_data(charger: FakeCloudCharger) -> FakeProductData:
    """Create cloud data of a charger that fulfils every precondition."""
    return FakeProductData(
        product=charger,
        state={
            "chargerFirmware": FIRMWARE_WITH_OCPP,
            "wiFiRSSI": -60,
            "operatorName": "Easee",
            "dynamicCircuitCurrentP1": 32,
            "dynamicCircuitCurrentP2": 32,
            "dynamicCircuitCurrentP3": 32,
        },
        config={
            "circuitMaxCurrentP1": 32,
            "circuitMaxCurrentP2": 32,
            "circuitMaxCurrentP3": 32,
        },
        circuit=FakeCircuit(),
    )


class FakeController:
    """Creates the charger devices like the cloud entities would, but no cloud entities."""

    chargers: list[FakeCloudCharger] = []
    chargers_data: list[FakeProductData] = []
    easee: FakeEaseeApi = FakeEaseeApi()

    def __init__(
        self,
        username: str,
        password: str,
        hass: HomeAssistant,
        config_entry: ConfigEntry,
    ) -> None:
        """Mirror the real constructor."""
        self.hass = hass
        self.entry = config_entry

    @classmethod
    def reset(cls, chargers: list[FakeCloudCharger]) -> None:
        """Fresh cloud with these chargers, all ready for OCPP."""
        cls.chargers = chargers
        cls.chargers_data = [ready_product_data(charger) for charger in chargers]
        cls.easee = FakeEaseeApi()

    @classmethod
    def product_data(cls, serial: Serial) -> FakeProductData:
        """Cloud data of one charger."""
        return next(data for data in cls.chargers_data if data.product.id == serial)

    async def async_initialize(self) -> None:
        """Register one device per charger."""
        registry = dr.async_get(self.hass)
        for charger in self.chargers:
            registry.async_get_or_create(
                config_entry_id=self.entry.entry_id,
                identifiers={(DOMAIN, charger.id)},
                name=charger.name,
                manufacturer="Easee",
            )

    async def async_cleanup(self) -> None:
        """Mirror the real cleanup."""
        self.hass.data[DOMAIN].pop("controller")

    async def async_setup_done(self, name: str) -> None:
        """Nothing to track."""

    def get_chargers(self) -> list[FakeCloudCharger]:
        """Chargers of the account."""
        return self.chargers

    def get_equalizers(self) -> list[Any]:
        """No equalizers."""
        return []

    def get_sites(self) -> list[dict[str, str]]:
        """One site."""
        return [{"name": "Home"}]

    def _no_entities(self) -> list[Any]:
        return []

    get_binary_sensor_entities = _no_entities
    get_button_entities = _no_entities
    get_light_entities = _no_entities
    get_sensor_entities = _no_entities
    get_switch_entities = _no_entities
