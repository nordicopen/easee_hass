""" Easee Connector class """
import asyncio
import json
import logging
from datetime import datetime, timedelta
from typing import List

from async_timeout import timeout
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_MONITORED_CONDITIONS
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady, Unauthorized
from homeassistant.helpers import aiohttp_client
from homeassistant.helpers.event import async_track_time_interval
from pyeasee import (
    Charger,
    ChargerConfig,
    ChargerState,
    ChargerStreamData,
    Circuit,
    DatatypesStreamData,
    Easee,
    Equalizer,
    EqualizerStreamData,
    Site,
)
from pyeasee.charger import ChargerSchedule
from pyeasee.exceptions import (
    AuthorizationFailedException,
    NotFoundException,
    ServerFailureException,
    TooManyRequestsException,
)

from .binary_sensor import ChargerBinarySensor, EqualizerBinarySensor
from .const import (
    CONF_MONITORED_EQ_CONDITIONS,
    CONF_MONITORED_SITES,
    CUSTOM_UNITS,
    CUSTOM_UNITS_TABLE,
    EASEE_EQ_ENTITIES,
    MANDATORY_EASEE_ENTITIES,
    OPTIONAL_EASEE_ENTITIES,
    PLATFORMS,
    TIMEOUT,
)
from .entity import convert_units_funcs
from .sensor import ChargerSensor, EqualizerSensor
from .switch import ChargerSwitch

_LOGGER = logging.getLogger(__name__)

SCAN_INTERVAL_STATE_SECONDS = 60
SCAN_INTERVAL_EQUALIZERS_SECONDS = 20
SCAN_INTERVAL_SCHEDULES_SECONDS = 600

MINIMUM_UPDATE = 0.05

OFFLINE_DELAY = 17 * 60


def check_value(data_type, reference, value):
    if (
        data_type != DatatypesStreamData.Double.value
        and data_type != DatatypesStreamData.Integer.value
    ):
        return True

    if abs(reference - value) > abs(reference * MINIMUM_UPDATE):
        return True

    return False


class EqualizerData:
    """Representation equalizer data."""

    def __init__(self, equalizer: Equalizer, site: Site):
        """Initialize the charger data."""
        self.product: Equalizer = equalizer
        self.site: Site = site
        self.state = []
        self.config = []

    def update_stream_data(self, data_type, data_id, value):
        now = datetime.utcnow().replace(microsecond=0)
        self.state["latestPulse"] = now
        _LOGGER.debug(f"Equalizer latestPulse update {now}")
        self.state["isOnline"] = True
        try:
            name = EqualizerStreamData(data_id).name
        except ValueError:
            # Unsupported data
            _LOGGER.debug(f"Unsupported data id {data_id} {value}")
            return False

        str = f"Equalizer callback {data_id} {name} {value}"
        _LOGGER.debug(str)

        if "_" in name:
            first, second = name.split("_")
            if first == "state":
                oldvalue = self.state[second]
                self.state[second] = value
                if check_value(data_type, oldvalue, value):
                    return True
            elif first == "config":
                if self.config[second] != value:
                    self.config[second] = value
                    return True

        return False


class ChargerData:
    """Representation charger data."""

    def __init__(self, charger: Charger, circuit: Circuit, site: Site):
        """Initialize the charger data."""
        self.product: Charger = charger
        self.circuit: Circuit = circuit
        self.site: Site = site
        self.state: List[ChargerState] = []
        self.config: List[ChargerConfig] = []
        self.schedule: List[ChargerSchedule] = []

    async def schedules_async_refresh(self):
        try:
            self.schedule = await self.product.get_basic_charge_plan()
        except (TooManyRequestsException, ServerFailureException):
            _LOGGER.debug("Got server error while fetching schedule")
        except NotFoundException:
            self.schedule = None

        _LOGGER.debug("Schedule: %s", self.schedule)

    def update_stream_data(self, data_type, data_id, value):
        now = datetime.utcnow().replace(microsecond=0)
        self.state["latestPulse"] = now
        _LOGGER.debug(f"Charger latestPulse update {now}")
        self.state["isOnline"] = True
        try:
            name = ChargerStreamData(data_id).name
        except ValueError:
            # Unsupported data
            _LOGGER.debug(f"Unsupported data id {data_id} {value}")
            return False

        str = f"Charger callback {data_id} {name} {value}"
        _LOGGER.debug(str)

        if "_" in name:
            first, second = name.split("_")

            if first == "state":
                oldvalue = self.state[second]
                self.state[second] = value
                if check_value(data_type, oldvalue, value):
                    return True
            elif first == "config":
                if self.config[second] != value:
                    self.config[second] = value
                    return True
            elif first == "schedule":
                value = json.loads(value)
                self.schedule["id"] = value.get("Id")
                self.schedule["chargeStartTime"] = datetime.utcfromtimestamp(
                    value.get("StartSchedule")
                )
                periods = value.get("Periods")
                self.schedule["chargeStopTime"] = datetime.utcfromtimestamp(
                    value.get("StartSchedule") + periods[len(periods) - 1][0]
                )
                if value.get("ProfileKind") == "Recurring":
                    self.schedule["repeat"] = True
                else:
                    self.schedule["repeat"] = False
                return True
            else:
                _LOGGER.debug("Unkonwn update type: %s", first)

        return False


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
        self.equalizers: List[Equalizer] = []
        self.equalizers_data: List[EqualizerData] = []
        self.switch_entities = []
        self.sensor_entities = []
        self.equalizer_sensor_entities = []
        self.equalizer_binary_sensor_entities = []

    async def initialize(self):
        """ initialize the session and get initial data """
        client_session = aiohttp_client.async_get_clientsession(self.hass)
        self.easee = Easee(self.username, self.password, client_session)

        try:
            with timeout(TIMEOUT):
                await self.easee.connect()
        except asyncio.TimeoutError as err:
            _LOGGER.debug("Connection to easee login timed out")
            raise ConfigEntryNotReady from err
        except ServerFailureException as err:
            _LOGGER.debug("Easee server failure")
            raise ConfigEntryNotReady from err
        except TooManyRequestsException as err:
            _LOGGER.debug("Easee server too many requests")
            raise ConfigEntryNotReady from err
        except AuthorizationFailedException as err:
            _LOGGER.error("Authorization failed to easee")
            raise Unauthorized from err
        except Exception:  # pylint: disable=broad-except
            _LOGGER.error("Unexpected error creating device")
            return None

        self.sites: List[Site] = await self.easee.get_sites()

        self.monitored_sites = self.config.options.get(
            CONF_MONITORED_SITES, [site.name for site in self.sites]
        )

        for site in self.sites:
            if site.name not in self.monitored_sites:
                _LOGGER.debug("Found site (unmonitored): %s %s", site.id, site.name)
            else:
                _LOGGER.debug("Found site (monitored): %s %s", site.id, site.name)
                for equalizer in site.get_equalizers():
                    _LOGGER.debug(
                        "Found equalizer: %s %s", equalizer.id, equalizer.name
                    )
                    self.equalizers.append(equalizer)
                    equalizer_data = EqualizerData(equalizer, site)
                    self.equalizers_data.append(equalizer_data)
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

        self._first_site_poll = True
        self._first_equalizer_poll = True
        self._first_schedule_poll = True
        self._init_count = 0
        self.running_loop = asyncio.get_running_loop()
        self.event_loop = asyncio.get_event_loop()

        self._create_entitites()

    async def stream_callback(self, id, data_type, data_id, value):
        for charger_data in self.chargers_data:
            if charger_data.product.id == id:
                if charger_data.update_stream_data(data_type, data_id, value):
                    _LOGGER.debug("Scheduling charger update")
                    self.update_ha_state()
                    return

        for equalizer_data in self.equalizers_data:
            if equalizer_data.product.id == id:
                if equalizer_data.update_stream_data(data_type, data_id, value):
                    _LOGGER.debug("Scheduling equalizer update")
                    self.update_equalizers_state()
                    return

    def setup_done(self, name):
        _LOGGER.debug(f"Entities {name} setup done")
        self._init_count = self._init_count + 1

        if self._init_count >= len(PLATFORMS) and self.running_loop is not None:
            asyncio.run_coroutine_threadsafe(self.add_schedulers(), self.event_loop)

    def update_ha_state(self):
        # Schedule an update for all other included entities
        all_entities = (
            self.switch_entities + self.sensor_entities + self.binary_sensor_entities
        )

        for entity in all_entities:
            entity.async_schedule_update_ha_state(True)

    def update_equalizers_state(self):
        # Schedule an update for all equalizer entities
        all_entities = (
            self.equalizer_sensor_entities + self.equalizer_binary_sensor_entities
        )
        for entity in all_entities:
            entity.async_schedule_update_ha_state(True)

    async def add_schedulers(self):
        """ Add schedules to udpate data """
        # first update
        tasks = [charger.schedules_async_refresh() for charger in self.chargers_data]
        if tasks:
            await asyncio.wait(tasks)
        self.hass.async_add_job(self.refresh_sites_state)
        self.hass.async_add_job(self.refresh_equalizers_state)

        # Add interval refresh for site state interval
        async_track_time_interval(
            self.hass,
            self.refresh_sites_state,
            timedelta(seconds=SCAN_INTERVAL_STATE_SECONDS),
        )

        # Add interval refresh for equalizer state interval
        async_track_time_interval(
            self.hass,
            self.refresh_equalizers_state,
            timedelta(seconds=SCAN_INTERVAL_EQUALIZERS_SECONDS),
        )

        # Add interval refresh for schedules
        async_track_time_interval(
            self.hass,
            self.refresh_schedules,
            timedelta(seconds=SCAN_INTERVAL_SCHEDULES_SECONDS),
        )

        for equalizer in self.equalizers:
            await self.easee.sr_subscribe(equalizer, self.stream_callback)
        for charger in self.chargers:
            await self.easee.sr_subscribe(charger, self.stream_callback)

    async def refresh_schedules(self, now=None):
        """ Refreshes the charging schedules data """
        if self._first_schedule_poll or not self.easee.sr_is_connected():
            self._first_schedule_poll = False

            tasks = [
                charger.schedules_async_refresh() for charger in self.chargers_data
            ]
            if tasks:
                await asyncio.wait(tasks)

        self.update_ha_state()

    async def refresh_sites_state(self, now=None):
        """ gets site state for all sites and updates the chargers state and config """
        sites_state = {}

        if not self._first_site_poll:
            for charger_data in self.chargers_data:
                elapsed = datetime.utcnow() - charger_data.state["latestPulse"]
                _LOGGER.debug(
                    f"Seconds since {charger_data.product.id} latestPulse {elapsed.total_seconds()}"
                )
                if elapsed.total_seconds() > OFFLINE_DELAY:
                    charger_data.state["isOnline"] = False

        if self._first_site_poll or not self.easee.sr_is_connected():
            self._first_site_poll = False

            for site in self.get_sites():
                if site.name in self.monitored_sites:
                    _LOGGER.debug("Getting state for site %s", site.id)
                    sites_state[site.id] = await self.easee.get_site_state(site.id)

            for charger_data in self.chargers_data:
                if charger_data.site.id not in sites_state:
                    _LOGGER.error(
                        "Site %s from charger not found in site states",
                        charger_data.state.id,
                    )
                    continue
                charger_id = charger_data.product.id
                site_state = sites_state[charger_data.site.id]

                charger_data.state = site_state.get_charger_state(charger_id, raw=True)
                _LOGGER.debug("Charger state: %s ", charger_id)
                charger_data.config = site_state.get_charger_config(
                    charger_id, raw=True
                )

        self.update_ha_state()

    async def refresh_equalizers_state(self, now=None):
        """ gets equalizer state for all equalizers """
        if not self._first_equalizer_poll:
            for equalizer_data in self.equalizers_data:
                elapsed = datetime.utcnow() - equalizer_data.state["latestPulse"]
                _LOGGER.debug(
                    f"Seconds since {equalizer_data.product.id} latestPulse {elapsed.total_seconds()}"
                )
                if elapsed.total_seconds() > OFFLINE_DELAY:
                    equalizer_data.state["isOnline"] = False

        if self._first_equalizer_poll or not self.easee.sr_is_connected():
            self._first_equalizer_poll = False
            for equalizer_data in self.equalizers_data:
                equalizer_data.state = await equalizer_data.product.get_state()

        self.update_equalizers_state()

    def get_sites(self):
        return self.sites

    def get_chargers(self):
        return self.chargers

    def get_circuits(self):
        return self.circuits

    def get_binary_sensor_entities(self):
        return self.binary_sensor_entities + self.equalizer_binary_sensor_entities

    def get_sensor_entities(self):
        return self.sensor_entities + self.equalizer_sensor_entities

    def get_switch_entities(self):
        return self.switch_entities

    def _create_entitites(self):
        monitored_conditions = list(
            dict.fromkeys(
                self.config.options.get(CONF_MONITORED_CONDITIONS, [])
                + [x for x in MANDATORY_EASEE_ENTITIES]
            )
        )
        monitored_eq_conditions = self.config.options.get(
            CONF_MONITORED_EQ_CONDITIONS, ["status"]
        )
        custom_units = self.config.options.get(CUSTOM_UNITS, {})
        self.sensor_entities = []
        self.switch_entities = []
        self.binary_sensor_entities = []
        self.equalizer_sensor_entities = []
        self.equalizer_binary_sensor_entities = []

        all_easee_entities = {**MANDATORY_EASEE_ENTITIES, **OPTIONAL_EASEE_ENTITIES}

        for charger_data in self.chargers_data:
            for key in monitored_conditions:
                # Fix renamed entities previously configured
                if key not in all_easee_entities:
                    continue
                data = all_easee_entities[key]
                entity_type = data.get("type", "sensor")

                if entity_type == "sensor":
                    _LOGGER.debug(
                        "Adding sensor entity: %s (%s) for charger %s",
                        key,
                        entity_type,
                        charger_data.product.name,
                    )

                    if data["units"] in custom_units:
                        data["units"] = CUSTOM_UNITS_TABLE[data["units"]]

                    self.sensor_entities.append(
                        ChargerSensor(
                            controller=self,
                            data=charger_data,
                            name=key,
                            state_key=data["key"],
                            units=data["units"],
                            convert_units_func=convert_units_funcs.get(
                                data["convert_units_func"], None
                            ),
                            attrs_keys=data["attrs"],
                            device_class=data["device_class"],
                            icon=data["icon"],
                            state_func=data.get("state_func", None),
                        )
                    )
                elif entity_type == "switch":
                    _LOGGER.debug(
                        "Adding switch entity: %s (%s) for charger %s",
                        key,
                        entity_type,
                        charger_data.product.name,
                    )
                    self.switch_entities.append(
                        ChargerSwitch(
                            controller=self,
                            data=charger_data,
                            name=key,
                            state_key=data["key"],
                            units=data["units"],
                            convert_units_func=convert_units_funcs.get(
                                data["convert_units_func"], None
                            ),
                            attrs_keys=data["attrs"],
                            device_class=data["device_class"],
                            icon=data["icon"],
                            state_func=data.get("state_func", None),
                            switch_func=data.get("switch_func", None),
                        )
                    )
                elif entity_type == "binary_sensor":
                    _LOGGER.debug(
                        "Adding binary sensor entity: %s (%s) for charger %s",
                        key,
                        entity_type,
                        charger_data.product.name,
                    )
                    self.binary_sensor_entities.append(
                        ChargerBinarySensor(
                            controller=self,
                            data=charger_data,
                            name=key,
                            state_key=data["key"],
                            units=data["units"],
                            convert_units_func=convert_units_funcs.get(
                                data["convert_units_func"], None
                            ),
                            attrs_keys=data["attrs"],
                            device_class=data["device_class"],
                            icon=data["icon"],
                            state_func=data.get("state_func", None),
                        )
                    )

        for equalizer_data in self.equalizers_data:
            for key in monitored_eq_conditions:
                # Fix renamed entities previously configured
                if key not in EASEE_EQ_ENTITIES:
                    continue
                data = EASEE_EQ_ENTITIES[key]
                entity_type = data.get("type", "sensor")

                if entity_type == "eq_sensor":
                    _LOGGER.debug(
                        "Adding sensor entity: %s (%s) for equalizer %s",
                        key,
                        entity_type,
                        equalizer_data.product.name,
                    )

                    if data["units"] in custom_units:
                        data["units"] = CUSTOM_UNITS_TABLE[data["units"]]

                    self.equalizer_sensor_entities.append(
                        EqualizerSensor(
                            controller=self,
                            data=equalizer_data,
                            name=key,
                            state_key=data["key"],
                            units=data["units"],
                            convert_units_func=convert_units_funcs.get(
                                data["convert_units_func"], None
                            ),
                            attrs_keys=data["attrs"],
                            device_class=data["device_class"],
                            icon=data["icon"],
                            state_func=data.get("state_func", None),
                        )
                    )

                elif entity_type == "eq_binary_sensor":
                    _LOGGER.debug(
                        "Adding binary sensor entity: %s (%s) for equalizer %s",
                        key,
                        entity_type,
                        equalizer_data.product.name,
                    )

                    if data["units"] in custom_units:
                        data["units"] = CUSTOM_UNITS_TABLE[data["units"]]

                    self.equalizer_binary_sensor_entities.append(
                        EqualizerBinarySensor(
                            controller=self,
                            data=equalizer_data,
                            name=key,
                            state_key=data["key"],
                            units=data["units"],
                            convert_units_func=convert_units_funcs.get(
                                data["convert_units_func"], None
                            ),
                            attrs_keys=data["attrs"],
                            device_class=data["device_class"],
                            icon=data["icon"],
                            state_func=data.get("state_func", None),
                        )
                    )
