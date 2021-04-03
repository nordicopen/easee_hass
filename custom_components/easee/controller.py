""" Easee Connector class """
import asyncio
import json
import logging
from datetime import datetime, timedelta
from gc import collect
from sys import getrefcount
from typing import List

from async_timeout import timeout
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_MONITORED_CONDITIONS
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady, Unauthorized
from homeassistant.helpers import aiohttp_client
from homeassistant.helpers.event import async_track_time_interval
from homeassistant.util import dt
from pyeasee import (
    Charger,
    ChargerStreamData,
    Circuit,
    DatatypesStreamData,
    Easee,
    Equalizer,
    EqualizerStreamData,
    Site,
)
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

ENTITY_TYPES = {
    "sensor": ChargerSensor,
    "binary_sensor": ChargerBinarySensor,
    "switch": ChargerSwitch,
    "eq_sensor": EqualizerSensor,
    "eq_binary_sensor": EqualizerBinarySensor,
}
_LOGGER = logging.getLogger(__name__)

SCAN_INTERVAL_STATE_SECONDS = 60
SCAN_INTERVAL_EQUALIZERS_SECONDS = 20
SCAN_INTERVAL_SCHEDULES_SECONDS = 600

MINIMUM_UPDATE = 0.05

OFFLINE_DELAY = 17 * 60


class ProductData:
    """Representation product data."""

    def __init__(self, product, site: Site, streamdata, circuit: Circuit = None):
        """Initialize the product data."""
        self.product = product
        self.circuit: Circuit = circuit
        self.site: Site = site
        self.state = None
        self.config = None
        self.schedule = None
        self.streamdata = streamdata
        self.dirty = False

    def is_state_polled(self):
        if self.state is None:
            return False
        return True

    def is_config_polled(self):
        if self.config is None:
            return False
        return True

    def is_schedule_polled(self):
        if self.schedule is None:
            return False
        return True

    def is_dirty(self):
        return self.dirty

    def mark_clean(self):
        self.dirty = False

    def mark_dirty(self):
        self.dirty = True

    async def schedules_async_refresh(self):
        try:
            self.schedule = await self.product.get_basic_charge_plan()
        except (TooManyRequestsException, ServerFailureException):
            _LOGGER.debug("Got server error while fetching schedule")
        except NotFoundException:
            self.schedule = None

        _LOGGER.debug("Schedule: %s", self.schedule)

    def check_value(self, data_type, reference, value):
        if (
            data_type != DatatypesStreamData.Double.value
            and data_type != DatatypesStreamData.Integer.value
        ):
            return True

        if abs(reference - value) > abs(reference * MINIMUM_UPDATE):
            return True

        return False

    def check_latest_pulse(self):
        if self.state is None:
            return

        now = dt.utcnow().replace(microsecond=0)
        elapsed = now - self.state["latestPulse"]

        if elapsed.total_seconds() > OFFLINE_DELAY:
            if self.state["isOnline"] is True:
                self.dirty = True
                self.state["isOnline"] = False
                _LOGGER.debug(f"Product {self.product.id} marked offline")

    def update_stream_data(self, data_type, data_id, value):
        if self.state is None:
            return False

        self.dirty = True
        now = dt.utcnow().replace(microsecond=0)
        self.state["latestPulse"] = now
        self.state["isOnline"] = True
        try:
            name = self.streamdata(data_id).name
        except ValueError:
            # Unsupported data
            _LOGGER.debug(f"Unsupported data id {data_id} {value}")
            return False

        _LOGGER.debug(f"Callback {self.product.id} {data_id} {name} {value}")

        if "_" in name:
            first, second = name.split("_")

            if first == "state":
                oldvalue = self.state[second]
                self.state[second] = value
                if self.check_value(data_type, oldvalue, value):
                    return True
            elif first == "config":
                if self.config is None:
                    return False
                if self.config[second] != value:
                    self.config[second] = value
                    return True
            elif first == "schedule":
                if self.schedule is None:
                    return False
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
        self.chargers_data: List[ProductData] = []
        self.equalizers: List[Equalizer] = []
        self.equalizers_data: List[ProductData] = []
        self.switch_entities = []
        self.sensor_entities = []
        self.equalizer_sensor_entities = []
        self.equalizer_binary_sensor_entities = []

    def __del__(self):
        _LOGGER.debug("Controller deleted")

    async def cleanup(self):
        if self.easee is not None:
            for equalizer in self.equalizers:
                await self.easee.sr_unsubscribe(equalizer)
            for charger in self.chargers:
                await self.easee.sr_unsubscribe(charger)
            await self.easee.close()
        for tracker in self.trackers:
            tracker()
        self.trackers = []
        collect()

        _LOGGER.debug("Controller refcount after cleanup %d", getrefcount(self))

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
                    equalizer_data = ProductData(equalizer, site, EqualizerStreamData)
                    self.equalizers_data.append(equalizer_data)
                for circuit in site.get_circuits():
                    _LOGGER.debug(
                        "Found circuit: %s %s", circuit.id, circuit["panelName"]
                    )
                    self.circuits.append(circuit)
                    for charger in circuit.get_chargers():
                        _LOGGER.debug("Found charger: %s %s", charger.id, charger.name)
                        self.chargers.append(charger)
                        charger_data = ProductData(
                            charger, site, ChargerStreamData, circuit
                        )
                        self.chargers_data.append(charger_data)

        self._init_count = 0
        self.running_loop = asyncio.get_running_loop()
        self.event_loop = asyncio.get_event_loop()
        self.trackers = []

        self._create_entitites()

    async def stream_callback(self, id, data_type, data_id, value):
        all_data = self.chargers_data + self.equalizers_data

        for data in all_data:
            if data.product.id == id:
                if data.update_stream_data(data_type, data_id, value):
                    _LOGGER.debug("Scheduling update")
                    self.update_ha_state()
                    return

    def setup_done(self, name):
        _LOGGER.debug(f"Entities {name} setup done")
        self._init_count = self._init_count + 1

        if self._init_count >= len(PLATFORMS) and self.running_loop is not None:
            asyncio.run_coroutine_threadsafe(self.add_schedulers(), self.event_loop)

    def update_ha_state(self):
        # Schedule an update for all other included entities
        all_entities = (
            self.switch_entities
            + self.sensor_entities
            + self.binary_sensor_entities
            + self.equalizer_sensor_entities
            + self.equalizer_binary_sensor_entities
        )

        for entity in all_entities:
            if entity.data.is_dirty():
                entity.async_schedule_update_ha_state(True)

        for entity in all_entities:
            entity.data.mark_clean()

    async def add_schedulers(self):
        """ Add schedules to udpate data """
        # first update
        tasks = [charger.schedules_async_refresh() for charger in self.chargers_data]
        if tasks:
            await asyncio.wait(tasks)
        self.hass.async_add_job(self.refresh_sites_state)
        self.hass.async_add_job(self.refresh_equalizers_state)

        # Add interval refresh for site state interval
        self.trackers.append(
            async_track_time_interval(
                self.hass,
                self.refresh_sites_state,
                timedelta(seconds=SCAN_INTERVAL_STATE_SECONDS),
            )
        )

        # Add interval refresh for equalizer state interval
        self.trackers.append(
            async_track_time_interval(
                self.hass,
                self.refresh_equalizers_state,
                timedelta(seconds=SCAN_INTERVAL_EQUALIZERS_SECONDS),
            )
        )

        # Add interval refresh for schedules
        self.trackers.append(
            async_track_time_interval(
                self.hass,
                self.refresh_schedules,
                timedelta(seconds=SCAN_INTERVAL_SCHEDULES_SECONDS),
            )
        )

        # Let other tasks run
        await asyncio.sleep(0)

        for equalizer in self.equalizers:
            await self.easee.sr_subscribe(equalizer, self.stream_callback)
        for charger in self.chargers:
            await self.easee.sr_subscribe(charger, self.stream_callback)

    async def refresh_schedules(self, now=None):
        """ Refreshes the charging schedules data """
        for charger in self.chargers_data:
            if charger.is_schedule_polled() and self.easee.sr_is_connected():
                continue
            await charger.schedules_async_refresh()

        self.update_ha_state()

    async def refresh_sites_state(self, now=None):
        """ gets site state for all sites and updates the chargers state and config """

        for charger_data in self.chargers_data:
            charger_data.check_latest_pulse()
            if charger_data.is_state_polled() and self.easee.sr_is_connected():
                continue

            site_state = await self.easee.get_site_state(charger_data.site.id)
            charger_id = charger_data.product.id

            charger_data.state = site_state.get_charger_state(charger_id, raw=True)
            _LOGGER.debug("Charger state: %s ", charger_id)
            charger_data.config = site_state.get_charger_config(charger_id, raw=True)
            charger_data.mark_dirty()

        self.update_ha_state()

    async def refresh_equalizers_state(self, now=None):
        """ gets equalizer state for all equalizers """

        for equalizer_data in self.equalizers_data:
            equalizer_data.check_latest_pulse()
            if equalizer_data.is_state_polled() and self.easee.sr_is_connected():
                continue
            equalizer_data.state = await equalizer_data.product.get_state()
            equalizer_data.config = await equalizer_data.product.get_config()
            equalizer_data.mark_dirty()

        self.update_ha_state()

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

    def _create_entity(
        self,
        object_type,
        controller,
        product_data,
        name,
        data,
    ):

        custom_units = self.config.options.get(CUSTOM_UNITS, {})
        if data["units"] in custom_units:
            data["units"] = CUSTOM_UNITS_TABLE[data["units"]]

        entity_type_name = ENTITY_TYPES[object_type]

        entity = entity_type_name(
            controller=controller,
            data=product_data,
            name=name,
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
        _LOGGER.debug(
            "Adding entity: %s (%s) for product %s",
            name,
            object_type,
            product_data.product.name,
        )
        if object_type == "sensor":
            self.sensor_entities.append(entity)

        elif object_type == "switch":
            self.switch_entities.append(entity)

        elif object_type == "binary_sensor":
            self.binary_sensor_entities.append(entity)

        elif object_type == "eq_sensor":
            self.equalizer_sensor_entities.append(entity)

        elif object_type == "eq_binary_sensor":
            self.equalizer_binary_sensor_entities.append(entity)

        return entity

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

                self._create_entity(
                    entity_type,
                    controller=self,
                    product_data=charger_data,
                    name=key,
                    data=data,
                )

        for equalizer_data in self.equalizers_data:
            for key in monitored_eq_conditions:
                # Fix renamed entities previously configured
                if key not in EASEE_EQ_ENTITIES:
                    continue
                data = EASEE_EQ_ENTITIES[key]
                entity_type = data.get("type", "eq_sensor")

                self._create_entity(
                    entity_type,
                    controller=self,
                    product_data=equalizer_data,
                    name=key,
                    data=data,
                )
