""" Easee Connector class """
import asyncio
from datetime import timedelta
from gc import collect
import json
import logging
from random import random
from sys import getrefcount
from typing import List

from async_timeout import timeout
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady, Unauthorized
from homeassistant.helpers import aiohttp_client
from homeassistant.helpers.event import (
    async_track_time_change,
    async_track_time_interval,
)
from homeassistant.util import dt
from pyeasee import (
    Charger,
    ChargerSchedule,
    ChargerStreamData,
    ChargerWeeklySchedule,
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
    CONF_MONITORED_SITES,
    DOMAIN,
    EASEE_EQ_ENTITIES,
    MANDATORY_EASEE_ENTITIES,
    OPTIONAL_EASEE_ENTITIES,
    PLATFORMS,
    TIMEOUT,
    chargerObservations,
    equalizerObservations,
    weeklyScheduleStartDays,
    weeklyScheduleStopDays,
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

    def __init__(
        self,
        product,
        site: Site,
        streamdata,
        poll_observations,
        circuit: Circuit = None,
        master=False,
    ):
        """Initialize the product data."""
        self.product = product
        self.circuit: Circuit = circuit
        self.site: Site = site
        self.state = None
        self.config = None
        self.schedule = None
        self.weekly_schedule = None
        self.cost_day = {"totalEnergyUsage": 0, "totalCost": 0, "currencyId": ""}
        self.cost_month = {"totalEnergyUsage": 0, "totalCost": 0, "currencyId": ""}
        self.cost_year = {"totalEnergyUsage": 0, "totalCost": 0, "currencyId": ""}
        self.schedule_polled = False
        self.streamdata = streamdata
        self.dirty = False
        self.poll_observations = poll_observations
        self.master = master
        self.firmware_auth_failure = None

    def is_state_polled(self):
        """Check if state is polled."""
        if self.state is None:
            return False
        return True

    def is_config_polled(self):
        """Check if config is polled."""
        if self.config is None:
            return False
        return True

    def is_schedule_polled(self):
        """Check if schedule is polled."""
        return self.schedule_polled

    def is_dirty(self):
        """Check if there are changes that needs to be sent to HA."""
        if self.state is None:
            return False
        if self.config is None:
            return False

        if "latestFirmware" not in self.state:
            return False

        return self.dirty

    def is_master(self):
        """Check if master."""
        return self.master

    def mark_clean(self):
        """Mark as clean."""
        self.dirty = False

    def mark_dirty(self):
        """Mark as dirty."""
        self.dirty = True

    async def firmware_async_refresh(self):
        """Poll latest firmware version."""
        if self.state is None:
            return False

        try:
            firmware = await self.product.get_latest_firmware()
        except AuthorizationFailedException as ex:
            if self.firmware_auth_failure is None:
                _LOGGER.error(
                    "Authorization failure when fetching firmware info: %s", ex
                )
                self.firmware_auth_failure = True
            self.state["latestFirmware"] = None
            return

        self.state["latestFirmware"] = firmware["latestFirmware"]
        _LOGGER.debug(
            "Latest Firmware for %s: %s", self.product.id, firmware["latestFirmware"]
        )

    async def async_refresh(self):
        """Poll observations."""
        if self.state is None:
            self.state = await self.product.empty_state(raw=True)
        if self.config is None:
            self.config = await self.product.empty_config(raw=True)

        self.state["voltageNL1"] = None
        self.state["voltageNL2"] = None
        self.state["voltageNL3"] = None
        self.state["voltageL1L2"] = None
        self.state["voltageL1L3"] = None
        self.state["voltageL2L3"] = None
        self.state["internalTemperature"] = None

        _LOGGER.debug(
            "Polling state for %s using %s", self.product.id, self.poll_observations
        )
        observations = await self.product.get_observations(*self.poll_observations)
        for observation in observations["observations"]:
            data_id = observation["id"]
            value = observation["value"]
            try:
                name = self.streamdata(data_id).name
            except ValueError:
                # Unsupported data
                _LOGGER.debug("Unsupported data id %s %s", data_id, value)
                return False

            _LOGGER.debug(
                "Observation %s %s type %s %s",
                name,
                value,
                observation["dataType"],
                type(value),
            )

            if "_" in name:
                first, second = name.split("_")

            if first == "state":
                self.state[second] = value
            elif first == "config":
                self.config[second] = value
            elif first == "schedule":
                if value == "":
                    value = "{}"
                self.schedules_interpret(json.loads(value))

    async def schedules_async_refresh(self):
        """Poll schedule data."""
        self.schedule_polled = True

        try:
            self.schedule = await self.product.get_basic_charge_plan()
        except (TooManyRequestsException, ServerFailureException):
            _LOGGER.error("Got server error while fetching schedule")
            self.schedule_polled = False
        except NotFoundException:
            self.schedule = None

        try:
            self.weekly_schedule = await self.product.get_weekly_charge_plan()
        except (TooManyRequestsException, ServerFailureException):
            _LOGGER.error("Got server error while fetching weekly schedule")
            self.schedule_polled = False
        except NotFoundException:
            self.weekly_schedule = None

        _LOGGER.debug("Schedule: %s %s", self.schedule, self.weekly_schedule)

    def schedules_interpret(self, data):
        """Interpret schedule data."""
        self.schedule_polled = True

        start_epoch = data.get("StartSchedule", 0)
        kind = data.get("ProfileKind")
        recurrency = data.get("RecurrencyKind")
        periods = data.get("Periods")

        self.schedule = ChargerSchedule({"isEnabled": False})
        self.weekly_schedule = ChargerWeeklySchedule({"isEnabled": False})

        # Weekly schedule
        if kind == "Recurring" and recurrency == "Weekly":
            self.weekly_schedule["isEnabled"] = True
            for period in periods:
                time = dt.as_local(dt.utc_from_timestamp(start_epoch + period[0]))
                day = time.weekday()
                if period[1] != 0:  # Start
                    saved_day = day
                    self.weekly_schedule[
                        weeklyScheduleStartDays[saved_day]
                    ] = time.strftime("%H:%M")
                else:
                    self.weekly_schedule[
                        weeklyScheduleStopDays[saved_day]
                    ] = time.strftime("%H:%M")
        # Delayed or Daily schedule
        elif (kind == "Recurring" and recurrency == "Daily") or kind == "Absolute":
            self.schedule["isEnabled"] = True
            self.schedule["repeat"] = kind == "Recurring"
            for period in periods:
                time = dt.as_local(dt.utc_from_timestamp(start_epoch + period[0]))
                if period[1] != 0:  # Start
                    self.schedule["chargeStartTime"] = time.strftime("%H:%M")
                else:
                    self.schedule["chargeStopTime"] = time.strftime("%H:%M")

    async def cost_async_refresh(self):
        """Poll cost data."""
        dt_end = dt.now().replace(microsecond=0)
        dt_start = dt.now().replace(hour=0, minute=0, second=0, microsecond=0)
        costs_day = await self.site.get_cost_between_dates(
            dt.as_utc(dt_start), dt.as_utc(dt_end)
        )
        dt_start = dt_start.replace(day=1)
        costs_month = await self.site.get_cost_between_dates(
            dt.as_utc(dt_start), dt.as_utc(dt_end)
        )
        dt_start = dt_start.replace(month=1)
        costs_year = await self.site.get_cost_between_dates(
            dt.as_utc(dt_start), dt.as_utc(dt_end)
        )
        _LOGGER.debug("Cost refreshed %s %s %s", costs_day, costs_month, costs_year)
        if costs_day is not None:
            for cost in costs_day:
                if cost["chargerId"] == self.product.id:
                    self.cost_day = cost
        if costs_month is not None:
            for cost in costs_month:
                if cost["chargerId"] == self.product.id:
                    self.cost_month = cost
        if costs_year is not None:
            for cost in costs_year:
                if cost["chargerId"] == self.product.id:
                    self.cost_year = cost

    def check_value(self, data_type, reference, value):
        """Check if recieved data is a change."""
        if (
            data_type != DatatypesStreamData.Double.value
            and data_type != DatatypesStreamData.Integer.value
        ):
            return True

        if abs(reference - value) > abs(reference * MINIMUM_UPDATE):
            return True

        return False

    def check_latest_pulse(self):
        """Check if product has timed out."""
        if self.state is None:
            return

        now = dt.utcnow().replace(microsecond=0)
        elapsed = now - self.state["latestPulse"]

        if elapsed.total_seconds() > OFFLINE_DELAY:
            if self.state["isOnline"] is True:
                self.dirty = True
                self.state["isOnline"] = False
                _LOGGER.debug("Product %s marked offline", self.product.id)

    def set_signalr_state(self, state):
        """Update status of SignalR stream."""
        if self.state is None:
            return

        self.state["signalRConnected"] = state

    async def update_stream_data(self, data_type, data_id, value):
        """Update data with received data from SignalR stream."""
        if self.state is None:
            return False

        self.state["signalRConnected"] = True
        self.dirty = True
        now = dt.utcnow().replace(microsecond=0)
        self.state["latestPulse"] = now
        self.state["isOnline"] = True
        try:
            name = self.streamdata(data_id).name
        except ValueError:
            # Unsupported data
            _LOGGER.debug("Unsupported data id %s %s", data_id, value)
            return False

        _LOGGER.debug(
            "Callback %s %s %s %s %s", self.product.id, data_id, name, value, data_type
        )

        if "_" in name:
            first, second = name.split("_")

            if first == "state":
                oldvalue = self.state[second]
                self.state[second] = value
                if second == "lifetimeEnergy" and oldvalue != value:
                    await self.cost_async_refresh()
                if self.check_value(data_type, oldvalue, value):
                    return True
            elif first == "config":
                if self.config is None:
                    return False
                if self.config[second] != value:
                    self.config[second] = value
                    return True
            elif first == "schedule":
                _LOGGER.debug("Schedule update")
                if value == "":
                    value = "{}"
                self.schedules_interpret(json.loads(value))
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
        self.easee: Easee | None = None
        self.sites: List[Site] = []
        self.circuits: List[Circuit] = []
        self.chargers: List[Charger] = []
        self.chargers_data: List[ProductData] = []
        self.equalizers: List[Equalizer] = []
        self.equalizers_data: List[ProductData] = []
        self.binary_sensor_entities = []
        self.switch_entities = []
        self.sensor_entities = []
        self.equalizer_sensor_entities = []
        self.equalizer_binary_sensor_entities = []
        self.diagnostics = {}
        self.trackers = []
        self.monitored_sites = None
        self._init_count = 0

    def __del__(self):
        _LOGGER.debug("Controller deleted")

    async def cleanup(self):
        """Cleanup controller."""
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
        """Initialize the session and get initial data."""
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

        try:
            self.sites: List[Site] = await self.easee.get_account_products()
            self.diagnostics["sites"] = self.sites

            self.monitored_sites = self.config.options.get(
                CONF_MONITORED_SITES, [site.name for site in self.sites]
            )

            for site in self.sites:
                if site.name not in self.monitored_sites:
                    _LOGGER.debug("Found site (unmonitored): %s %s", site.id, site.name)
                else:
                    _LOGGER.debug("Found site (monitored): %s %s", site.id, site.name)
                    equalizers = site.get_equalizers()
                    for equalizer in equalizers:
                        _LOGGER.debug(
                            "Found equalizer: %s %s", equalizer.id, equalizer.name
                        )
                        self.equalizers.append(equalizer)
                        equalizer_data = ProductData(
                            equalizer,
                            site,
                            EqualizerStreamData,
                            equalizerObservations,
                        )
                        self.equalizers_data.append(equalizer_data)
                    circuits = site.get_circuits()
                    for circuit in circuits:
                        _LOGGER.debug(
                            "Found circuit: %s %s %s",
                            circuit.id,
                            circuit["panelName"],
                            circuit.get_data(),
                        )
                        self.circuits.append(circuit)
                        for charger in circuit.get_chargers():
                            if charger.id is not None:
                                _LOGGER.debug(
                                    "Found charger: %s %s %s",
                                    charger.id,
                                    charger.name,
                                    charger.get_data(),
                                )
                                master = False
                                back_plate = charger["backPlate"]
                                if back_plate["id"] == back_plate["masterBackPlateId"]:
                                    master = True
                                self.chargers.append(charger)
                                charger_data = ProductData(
                                    charger,
                                    site,
                                    ChargerStreamData,
                                    chargerObservations,
                                    circuit,
                                    master=master,
                                )
                                self.chargers_data.append(charger_data)

            self.hass.data[DOMAIN]["diagnostics"] = self.diagnostics
            self._init_count = 0
            self.trackers = []

            self._create_entitites()

        except Exception as err:
            _LOGGER.debug("Easee server failure %s", err)
            raise ConfigEntryNotReady from err

    async def stream_callback(self, idx, data_type, data_id, value):
        """The stream callback."""
        all_data = self.chargers_data + self.equalizers_data

        for data in all_data:
            if data.product.id == idx:
                if await data.update_stream_data(data_type, data_id, value):
                    _LOGGER.debug("Scheduling update")
                    self.update_ha_state()
                    return

    async def setup_done(self, name):
        """Entities setup is done."""
        _LOGGER.debug("Entities %s setup done", name)
        self._init_count = self._init_count + 1

        if self._init_count >= len(PLATFORMS):
            await self.add_schedulers()

    def update_ha_state(self):
        """Schedule an update for all other included entities."""
        all_entities = (
            self.switch_entities
            + self.sensor_entities
            + self.binary_sensor_entities
            + self.equalizer_sensor_entities
            + self.equalizer_binary_sensor_entities
        )

        for entity in all_entities:
            if entity.enabled and entity.data.is_dirty():
                entity.async_schedule_update_ha_state(True)

        for entity in all_entities:
            entity.data.mark_clean()

    async def add_schedulers(self):
        """Add schedules to update data"""
        # first update
        await self.refresh_sites_state()
        await self.refresh_equalizers_state()
        await asyncio.gather(
            *[charger.cost_async_refresh() for charger in self.chargers_data]
        )
        await asyncio.gather(
            *[charger.firmware_async_refresh() for charger in self.chargers_data]
        )
        await asyncio.gather(
            *[equalizer.firmware_async_refresh() for equalizer in self.equalizers_data]
        )

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

        # Add time pattern refresh some random time after midnight
        self.trackers.append(
            async_track_time_change(
                self.hass,
                self.refresh_midnight,
                hour=0,
                minute=int(random() * 9),
                second=int(random() * 59),
            )
        )

        # Let other tasks run
        await asyncio.sleep(0)

        for equalizer in self.equalizers:
            await self.easee.sr_subscribe(equalizer, self.stream_callback)
        for charger in self.chargers:
            await self.easee.sr_subscribe(charger, self.stream_callback)

    async def refresh_midnight(self, now=None):
        """Refreshes the cost data"""
        _LOGGER.debug("Midnight refresh started")
        for charger in self.chargers_data:
            await charger.cost_async_refresh()
            await charger.firmware_async_refresh()

        for equalizer in self.equalizers_data:
            await equalizer.firmware_async_refresh()

        self.update_ha_state()

    async def refresh_schedules(self, now=None):
        """Refreshes the charging schedules data"""
        for charger in self.chargers_data:
            if charger.is_schedule_polled() and self.easee.sr_is_connected():
                continue
            await charger.schedules_async_refresh()

        self.update_ha_state()

    async def refresh_sites_state(self, now=None):
        """gets site state for all sites and updates the chargers state and config"""

        for charger_data in self.chargers_data:
            charger_data.set_signalr_state(self.easee.sr_is_connected())
            charger_data.check_latest_pulse()
            if charger_data.is_state_polled() and self.easee.sr_is_connected():
                continue

            await charger_data.async_refresh()
            charger_data.set_signalr_state(self.easee.sr_is_connected())
            charger_data.mark_dirty()

        self.update_ha_state()

    async def refresh_equalizers_state(self, now=None):
        """gets equalizer state for all equalizers"""

        for equalizer_data in self.equalizers_data:
            equalizer_data.set_signalr_state(self.easee.sr_is_connected())
            equalizer_data.check_latest_pulse()
            if equalizer_data.is_state_polled() and self.easee.sr_is_connected():
                continue

            await equalizer_data.async_refresh()
            equalizer_data.set_signalr_state(self.easee.sr_is_connected())
            equalizer_data.mark_dirty()

        self.update_ha_state()

    def get_sites(self):
        """Get sites."""
        return self.sites

    def get_chargers(self):
        """Get chargers."""
        return self.chargers

    def check_circuit_current(
        self,
        circuit_id,
        current_p1,
        current_p2,
        current_p3,
        compare_p1,
        compare_p2,
        compare_p3,
    ):
        """Check circuit current."""
        if current_p2 is None:
            current_p2 = current_p1
        if current_p3 is None:
            current_p3 = current_p1

        for charger_data in self.chargers_data:
            if charger_data.circuit.id == circuit_id:
                try:
                    if (
                        charger_data.state[compare_p1] != current_p1
                        or charger_data.state[compare_p2] != current_p2
                        or charger_data.state[compare_p3] != current_p3
                    ):
                        return charger_data.circuit
                except KeyError:
                    if (
                        charger_data.config[compare_p1] != current_p1
                        or charger_data.config[compare_p2] != current_p2
                        or charger_data.config[compare_p3] != current_p3
                    ):
                        return charger_data.circuit

                return False
        return None

    def check_charger_current(
        self,
        charger_id,
        current_p1,
        current_p2,
        current_p3,
        compare_p1,
        compare_p2,
        compare_p3,
    ):
        """Check charger current."""
        if current_p2 is None:
            current_p2 = current_p1
        if current_p3 is None:
            current_p3 = current_p1

        for charger_data in self.chargers_data:
            if charger_data.product.id == charger_id:
                try:
                    if (
                        charger_data.state[compare_p1] != current_p1
                        or charger_data.state[compare_p2] != current_p2
                        or charger_data.state[compare_p3] != current_p3
                    ):
                        return charger_data.product
                except KeyError:
                    if (
                        charger_data.config[compare_p1] != current_p1
                        or charger_data.config[compare_p2] != current_p2
                        or charger_data.config[compare_p3] != current_p3
                    ):
                        return charger_data.product

                return False
        return None

    def get_circuits(self):
        """Get the circuits."""
        return self.circuits

    def get_binary_sensor_entities(self):
        """Get binary sensor entities."""
        return self.binary_sensor_entities + self.equalizer_binary_sensor_entities

    def get_sensor_entities(self):
        """Get sensor entities."""
        return self.sensor_entities + self.equalizer_sensor_entities

    def get_switch_entities(self):
        """Return switch_entities."""
        return self.switch_entities

    def _create_entity(
        self,
        object_type,
        controller,
        product_data,
        name,
        data,
    ):
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
            translation_key=data.get("translation_key"),
            suggested_display_precision=data.get("suggested_display_precision"),
            state_class=data.get("state_class", None),
            icon=data["icon"],
            state_func=data.get("state_func", None),
            switch_func=data.get("switch_func", None),
            enabled_default=data.get("enabled_default", True),
            entity_category=data.get("entity_category", None),
        )
        _LOGGER.debug(
            "Adding entity: %s (%s) for product %s, unit %s",
            name,
            object_type,
            product_data.product.name,
            data["units"],
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
        self.sensor_entities = []
        self.switch_entities = []
        self.binary_sensor_entities = []
        self.equalizer_sensor_entities = []
        self.equalizer_binary_sensor_entities = []

        all_easee_entities = {**MANDATORY_EASEE_ENTITIES, **OPTIONAL_EASEE_ENTITIES}

        for charger_data in self.chargers_data:
            is_slave = not charger_data.is_master()
            for key, data in all_easee_entities.items():
                entity_type = data.get("type", "sensor")
                only_master = data.get("only_master", False)
                if is_slave and only_master:
                    continue
                self._create_entity(
                    entity_type,
                    controller=self,
                    product_data=charger_data,
                    name=key,
                    data=data,
                )

        for equalizer_data in self.equalizers_data:
            for key, data in EASEE_EQ_ENTITIES.items():
                entity_type = data.get("type", "eq_sensor")

                self._create_entity(
                    entity_type,
                    controller=self,
                    product_data=equalizer_data,
                    name=key,
                    data=data,
                )
