"""Shared fixtures for Easee EV charger tests."""

from collections.abc import Callable
from typing import Any
from unittest.mock import MagicMock

from pyeasee import Charger, ChargerStreamData, Circuit, Site
import pytest

from custom_components.easee.const import (
    MANDATORY_EASEE_ENTITIES,
    OPTIONAL_EASEE_ENTITIES,
    chargerObservations,
)
from custom_components.easee.controller import ENTITY_TYPES, ProductData, UserData
from custom_components.easee.entity import ChargerEntity, convert_units_funcs


@pytest.fixture
def mock_site() -> Site:
    """Return a mock Easee Site."""
    return Site(
        {
            "id": 1001,
            "name": "Home Site",
            "siteKey": "SITE-KEY-1",
            "ratedCurrent": 25.0,
            "costPerKWh": 0.30,
            "costPerKwhExcludeVat": 0.25,
            "vat": 20.0,
            "currencyId": "EUR",
        },
        easee=MagicMock(),
    )


@pytest.fixture
def mock_circuit(mock_site: Site) -> Circuit:
    """Return a mock Easee Circuit."""
    return Circuit(
        {
            "id": 2001,
            "circuitPanelId": 1,
            "panelName": "Carport Panel",
            "ratedCurrent": 16.0,
        },
        site=mock_site,
        easee=MagicMock(),
    )


@pytest.fixture
def mock_charger(mock_site: Site, mock_circuit: Circuit) -> Charger:
    """Return a mock Easee Charger."""
    return Charger(
        {
            "id": "EH123456",
            "name": "Carport",
            "productCode": 1,
            "levelOfAccess": 1,
            "userRole": 1,
        },
        easee=MagicMock(),
        site=mock_site,
        circuit=mock_circuit,
    )


@pytest.fixture
def product_data(
    mock_charger: Charger, mock_site: Site, mock_circuit: Circuit
) -> ProductData:
    """Return a ProductData instance for a master charger."""
    return ProductData(
        product=mock_charger,
        site=mock_site,
        user_data=UserData(),
        streamdata=ChargerStreamData,
        poll_observations=chargerObservations,
        circuit=mock_circuit,
        master=True,
        cost_data=None,
    )


@pytest.fixture
def create_entity(
    product_data: ProductData,
) -> Callable[[str, dict[str, Any] | None], ChargerEntity]:
    """Return a factory creating an integration entity from const definitions."""
    all_entities = {
        **MANDATORY_EASEE_ENTITIES,
        **OPTIONAL_EASEE_ENTITIES,
    }

    def _create(
        name: str,
        entity_def: dict[str, Any] | None = None,
        default_type: str = "sensor",
    ) -> ChargerEntity:
        data = entity_def if entity_def is not None else all_entities[name]
        object_type = data.get("type", default_type)
        entity_cls = ENTITY_TYPES[object_type]
        return entity_cls(
            data=product_data,
            name=name,
            state_key=data["key"],
            units=data["units"],
            convert_units_func=convert_units_funcs.get(data["convert_units_func"]),
            attrs_keys=data["attrs"],
            device_class=data["device_class"],
            translation_key=data.get("translation_key"),
            suggested_display_precision=data.get("suggested_display_precision"),
            state_class=data.get("state_class"),
            state_func=data.get("state_func"),
            switch_func=data.get("switch_func"),
            enabled_default=data.get("enabled_default", True),
            entity_category=data.get("entity_category"),
        )

    return _create
