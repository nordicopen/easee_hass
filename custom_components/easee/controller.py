""" Easee Connector class """
import asyncio
from typing import List, Dict, Callable, Any
from datetime import datetime, timedelta

from easee import Easee, Charger, ChargerState, ChargerConfig, Site, Circuit

from homeassistant.core import HomeAssistant
from homeassistant.config_entries import ConfigEntry
from homeassistant.helpers.entity import Entity
from homeassistant.util import dt
from homeassistant.helpers import aiohttp_client
from homeassistant.helpers.event import async_track_time_interval

from .const import (
    CONF_MONITORED_SITES,
    DOMAIN,
    EASEE_ENTITIES,
    LISTENER_FN_CLOSE,
    MEASURED_CONSUMPTION_DAYS,
    VERSION,
    PLATFORMS,
    SCAN_INTERVAL_SECONDS,
)

import logging

_LOGGER = logging.getLogger(__name__)

SCAN_INTERVAL = timedelta(seconds=SCAN_INTERVAL_SECONDS)


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

        all_sites = []
        for site in self.sites:
            all_sites.append(site["name"])

        monitored_sites = self.config.options.get(CONF_MONITORED_SITES, all_sites)

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

        self.hass.data[DOMAIN]["chargers_data"] = self.chargers_data
        self.hass.data[DOMAIN]["chargers"] = self.chargers
        self.hass.data[DOMAIN]["circuits"] = self.circuits
        self.hass.data[DOMAIN]["config"] = self.config
        self.hass.data[DOMAIN]["chargers"] = self.chargers
        self.hass.data[DOMAIN]["circuits"] = self.circuits

        self.hass.async_add_job(self.chargers_data.async_refresh)
        async_track_time_interval(
            self.hass, self.chargers_data.async_refresh, SCAN_INTERVAL
        )
