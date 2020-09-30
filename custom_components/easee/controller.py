""" Easee Connector class """
import asyncio
from typing import Any, List
from datetime import timedelta

from easee import Easee, Charger, ChargerState, ChargerConfig, Site, Circuit
from easee.charger import ChargerSchedule

from homeassistant.core import HomeAssistant
from homeassistant.config_entries import ConfigEntry
from homeassistant.helpers import aiohttp_client
from homeassistant.helpers.event import async_track_time_interval
from homeassistant.const import (
    CONF_MONITORED_CONDITIONS,
    ENERGY_KILO_WATT_HOUR,
)

from .const import (
    CONF_MONITORED_SITES,
    EASEE_ENTITIES,
    MEASURED_CONSUMPTION_DAYS,
    CUSTOM_UNITS,
    CUSTOM_UNITS_TABLE,
)

from .sensor import ChargerSensor, ChargerConsumptionSensor
from .switch import ChargerSwitch

from .entity import convert_units_funcs

import logging

_LOGGER = logging.getLogger(__name__)

SCAN_INTERVAL_SECONDS = 60


class ChargerData:
    """Representation charger data."""

    def __init__(self, charger: Charger, circuit: Circuit, site: Site):
        """Initialize the charger data."""
        self.charger: Charger = charger
        self.circuit: Circuit = circuit
        self.site: Site = site
        self.state: List[ChargerState] = []
        self.config: List[ChargerConfig] = []
        self.schedule: List[ChargerSchedule] = []

    async def async_refresh(self, now=None):
        self.state = await self.charger.get_state()
        self.config = await self.charger.get_config()
        self.schedule = await self.charger.get_basic_charge_plan()
        _LOGGER.debug("Schedule: %s", self.schedule)


class ChargersData:
    """Representation chargers data."""

    def __init__(self, chargers: List[ChargerData], entities: List[Any]):
        """Initialize the chargers data."""
        self._chargers = chargers
        self._entities = entities

    async def async_refresh(self, now=None):
        """Fetch new state data for the entities."""
        tasks = [charger.async_refresh() for charger in self._chargers]
        if tasks:
            await asyncio.wait(tasks)

        # Schedule an update for all included entities
        for entity in self._entities:
            entity.async_schedule_update_ha_state(True)


class Controller:
    """Controller class orchestrating the data fetching and entitities"""

    def __init__(
        self, username: str, password: str, hass: HomeAssistant, entry: ConfigEntry
    ):
        self.username = username
        self.password = password
        self.hass = hass
        self.config = entry
        self.session: Easee = None
        self.sites: List[Site] = []
        self.circuits: List[Circuit] = []
        self.chargers: List[Charger] = []
        self.chargers_data: ChargersData = None

    async def initialize(self):
        """ initialize the session and get initial data """
        client_session = aiohttp_client.async_get_clientsession(self.hass)
        self.easee = Easee(self.username, self.password, client_session)

        self.sites: List[Site] = await self.easee.get_sites()

        entities = []
        charger_data_list = []

        monitored_sites = self.config.options.get(
            CONF_MONITORED_SITES, [site["name"] for site in self.sites]
        )

        for site in self.sites:
            if not site["name"] in monitored_sites:
                _LOGGER.debug("Found site (unmonitored): %s %s", site.id, site["name"])
            else:
                _LOGGER.debug("Found site (monitored): %s %s", site.id, site["name"])
                for circuit in site.get_circuits():
                    _LOGGER.debug(
                        "Found circuit: %s %s", circuit.id, circuit["panelName"]
                    )
                    self.circuits.append(circuit)
                    for charger in circuit.get_chargers():
                        _LOGGER.debug("Found charger: %s %s", charger.id, charger.name)
                        self.chargers.append(charger)
                        charger_data = ChargerData(charger, circuit, site)
                        charger_data_list.append(charger_data)

        self.chargers_data = ChargersData(charger_data_list, entities)

        self._create_entitites()

    async def add_schedulers(self):
        # first update
        self.hass.async_add_job(self.chargers_data.async_refresh)

        # Add interval refresh for chargers
        async_track_time_interval(
            self.hass,
            self.chargers_data.async_refresh,
            timedelta(seconds=SCAN_INTERVAL_SECONDS),
        )

    def get_sites(self):
        return self.sites

    def get_chargers(self):
        return self.chargers

    def get_circuits(self):
        return self.circuits

    def get_sensor_entities(self):
        return self.sensor_entities + self.consumption_sensor_entities

    def get_switch_entities(self):
        return self.switch_entities

    def _create_entitites(self):
        chargers_data = self.chargers_data
        monitored_conditions = self.config.options.get(
            CONF_MONITORED_CONDITIONS, ["status"]
        )
        custom_units = self.config.options.get(CUSTOM_UNITS, {})
        sensor_entities = []
        switch_entities = []
        consumption_sensor_entities = []

        for charger_data in chargers_data._chargers:
            for key in monitored_conditions:
                data = EASEE_ENTITIES[key]
                entity_type = data.get("type", "sensor")

                if entity_type == "sensor":
                    _LOGGER.debug(
                        "Adding sensor entity: %s (%s) for charger %s",
                        key,
                        entity_type,
                        charger_data.charger.name,
                    )

                    if data["units"] in custom_units:
                        data["units"] = CUSTOM_UNITS_TABLE[data["units"]]

                    sensor_entities.append(
                        ChargerSensor(
                            charger_data=charger_data,
                            name=key,
                            state_key=data["key"],
                            units=data["units"],
                            convert_units_func=convert_units_funcs.get(
                                data["convert_units_func"], None
                            ),
                            attrs_keys=data["attrs"],
                            icon=data["icon"],
                            state_func=data.get("state_func", None),
                        )
                    )
                elif entity_type == "switch":
                    _LOGGER.debug(
                        "Adding switch entity: %s (%s) for charger %s",
                        key,
                        entity_type,
                        charger_data.charger.name,
                    )
                    switch_entities.append(
                        ChargerSwitch(
                            charger_data=charger_data,
                            name=key,
                            state_key=data["key"],
                            units=data["units"],
                            convert_units_func=convert_units_funcs.get(
                                data["convert_units_func"], None
                            ),
                            attrs_keys=data["attrs"],
                            icon=data["icon"],
                            state_func=data.get("state_func", None),
                            switch_func=data.get("switch_func", None),
                        )
                    )

            # Add consumption sensors
            monitored_days = self.config.options.get(MEASURED_CONSUMPTION_DAYS, [])
            consumption_unit = (
                CUSTOM_UNITS_TABLE[ENERGY_KILO_WATT_HOUR]
                if ENERGY_KILO_WATT_HOUR in custom_units
                else ENERGY_KILO_WATT_HOUR
            )
            for interval in monitored_days:
                _LOGGER.info("Will measure days: %s", interval)
                consumption_sensor_entities.append(
                    ChargerConsumptionSensor(
                        charger_data.charger,
                        f"consumption_days_{interval}",
                        int(interval),
                        consumption_unit,
                    )
                )

        self.sensor_entities = sensor_entities
        self.consumption_sensor_entities = consumption_sensor_entities
        self.switch_entities = switch_entities

        chargers_data._entities.extend(sensor_entities)
        chargers_data._entities.extend(switch_entities)

        # this should not be polled by our refresh but it seems the update it slow so need to check it
        # chargers_data._entities.extend(consumption_sensor_entities)
