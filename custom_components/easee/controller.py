""" Easee Connector class """
import asyncio
from typing import List
from datetime import timedelta

from easee import Easee, Charger, ChargerState, ChargerConfig, Site, Circuit
from easee.exceptions import NotFoundException
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

SCAN_INTERVAL_STATE_SECONDS = 60
SCAN_INTERVAL_SCHEDULES_SECONDS = 600


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

    async def schedules_async_refresh(self):
        try:
            self.schedule = await self.charger.get_basic_charge_plan()
        except NotFoundException:
            self.schedule = None

        _LOGGER.debug("Schedule: %s", self.schedule)


class Controller:
    """Controller class orchestrating the data fetching and entitities"""

    def __init__(
        self, username: str, password: str, hass: HomeAssistant, entry: ConfigEntry
    ):
        self.username = username
        self.password = password
        self.hass = hass
        self.config = entry
        self.easee: Easee = None
        self.sites: List[Site] = []
        self.circuits: List[Circuit] = []
        self.chargers: List[Charger] = []
        self.chargers_data: List[ChargerData] = []
        self.switch_entities = []
        self.sensor_entities = []

    async def initialize(self):
        """ initialize the session and get initial data """
        client_session = aiohttp_client.async_get_clientsession(self.hass)
        self.easee = Easee(self.username, self.password, client_session)
        await self.easee.connect()

        self.sites: List[Site] = await self.easee.get_sites()

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
                        self.chargers_data.append(charger_data)

        self._create_entitites()

    def update_ha_state(self):
        # Schedule an update for all included entities
        all_entities = (
            self.switch_entities
            + self.sensor_entities
            + self.consumption_sensor_entities
        )

        for entity in all_entities:
            entity.async_schedule_update_ha_state(True)

    async def add_schedulers(self):
        """ Add schedules to udpate data """
        # first update
        self.hass.async_add_job(self.refresh_schedules)
        self.hass.async_add_job(self.refresh_sites_state)

        # Add interval refresh for site state interval
        async_track_time_interval(
            self.hass,
            self.refresh_sites_state,
            timedelta(seconds=SCAN_INTERVAL_STATE_SECONDS),
        )

        # Add interval refresh for schedules interval
        async_track_time_interval(
            self.hass,
            self.refresh_schedules,
            timedelta(seconds=SCAN_INTERVAL_SCHEDULES_SECONDS),
        )

    async def refresh_schedules(self, now=None):
        """ Refreshes the charging schedules data """
        tasks = [charger.schedules_async_refresh() for charger in self.chargers_data]
        if tasks:
            await asyncio.wait(tasks)
        self.update_ha_state()

    async def refresh_sites_state(self, now=None):
        """ gets site state for all sites and updates the chargers state and config """
        sites_state = {}

        for site in self.get_sites():
            _LOGGER.debug("Getting state for site %s", site.id)
            sites_state[site.id] = await self.easee.get_site_state(site.id)

        for charger_data in self.chargers_data:
            if charger_data.site.id not in sites_state:
                _LOGGER.error(
                    "Site %s from charger not found in site states",
                    charger_data.state.id,
                )
                continue
            charger_id = charger_data.charger.id
            site_state = sites_state[charger_data.site.id]

            charger_data.state = site_state.get_charger_state(charger_id)
            charger_data.config = site_state.get_charger_config(charger_id)

        self.update_ha_state()

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
        monitored_conditions = self.config.options.get(
            CONF_MONITORED_CONDITIONS, ["status"]
        )
        custom_units = self.config.options.get(CUSTOM_UNITS, {})
        self.sensor_entities = []
        self.switch_entities = []
        self.consumption_sensor_entities = []

        for charger_data in self.chargers_data:
            for key in monitored_conditions:
                # Fix renamed entities previously configured
                if key not in EASEE_ENTITIES:
                    continue
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

                    self.sensor_entities.append(
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
                    self.switch_entities.append(
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
                self.consumption_sensor_entities.append(
                    ChargerConsumptionSensor(
                        charger_data.charger,
                        f"consumption_days_{interval}",
                        int(interval),
                        consumption_unit,
                    )
                )
