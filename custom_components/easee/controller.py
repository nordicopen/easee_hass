"""Easee Connector class."""

import asyncio
from collections import deque
from datetime import timedelta
from gc import collect
import json
import logging
from random import random

from pyeasee import (
    Charger,
    ChargerSchedule,
    ChargerStreamData,
    ChargerWeeklySchedule,
    Circuit,
    Easee,
    Equalizer,
    EqualizerStreamData,
    Site,
)
from pyeasee.exceptions import (
    AuthorizationFailedException,
    BadRequestException,
    ServerFailureException,
    TooManyRequestsException,
)

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import CALLBACK_TYPE, HomeAssistant, callback
from homeassistant.exceptions import ConfigEntryAuthFailed, ConfigEntryNotReady
from homeassistant.helpers import aiohttp_client
from homeassistant.helpers.event import (
    async_track_time_change,
    async_track_time_interval,
)
from homeassistant.util import dt as dt_util
from homeassistant.util.ssl import get_default_context

from .binary_sensor import ChargerBinarySensor, EqualizerBinarySensor
from .button import ChargerButton
from .const import (
    CONF_MONITORED_SITES,
    DOMAIN,
    EASEE_EQ_ENTITIES,
    MANDATORY_EASEE_ENTITIES,
    OPTIONAL_EASEE_ENTITIES,
    PLATFORMS,
    TIMEOUT,
    VERSION,
    chargerObservations,
    equalizerObservations,
    weeklyScheduleLimit,
    weeklyScheduleStartDays,
    weeklyScheduleStopDays,
)
from .entity import convert_units_funcs
from .light import ChargerLight
from .sensor import ChargerSensor, EqualizerSensor
from .switch import ChargerSwitch, EqualizerSwitch

ENTITY_TYPES = {
    "sensor": ChargerSensor,
    "binary_sensor": ChargerBinarySensor,
    "button": ChargerButton,
    "light": ChargerLight,
    "switch": ChargerSwitch,
    "eq_sensor": EqualizerSensor,
    "eq_binary_sensor": EqualizerBinarySensor,
    "eq_switch": EqualizerSwitch,
}
_LOGGER = logging.getLogger(__name__)

SCAN_INTERVAL_STATE_SECONDS = 60
SCAN_INTERVAL_EQUALIZERS_SECONDS = 20
SCAN_INTERVAL_SCHEDULES_SECONDS = 600

MINIMUM_UPDATE = 0.05

OFFLINE_DELAY = 17 * 60


class CostData:
    """Representation of Cost data."""

    def __init__(
        self,
        site: Site,
        period: int,
    ):
        """Initialize the cost data."""
        self.site: Site = site
        self.period: int = period
        self.request_logs = deque()
        self.observers = {}
        self.task = None

    def register_for_update(self, product_id, cost_callback):
        """Register callback for data update."""
        self.observers[product_id] = cost_callback
        _LOGGER.debug("Cost refresh callback registered.")

    def request_update(self, product_id):
        """Add a request to queue."""
        self.request_logs.append(product_id)
        self.task = asyncio.create_task(
            self.request_handler(), name="easee_hass cost update task"
        )
        _LOGGER.debug("Cost refresh requested.")

    async def request_handler(self):
        """Update cost data task."""
        await asyncio.sleep(self.period)
        if self.request_logs:
            _LOGGER.debug("Refreshing cost for %s.", self.request_logs)
            self.request_logs.clear()
            await self.update_cost()
        _LOGGER.debug("End of cost update task.")

    async def update_cost(self):
        """Poll cost data and notify observers."""
        dt_end = dt_util.now().replace(microsecond=0)
        dt_start = dt_util.now().replace(hour=0, minute=0, second=0, microsecond=0)
        costs_day = await self.site.get_cost_between_dates(
            dt_util.as_utc(dt_start), dt_util.as_utc(dt_end)
        )
        await asyncio.sleep(1)
        dt_start = dt_start.replace(day=1)
        costs_month = await self.site.get_cost_between_dates(
            dt_util.as_utc(dt_start), dt_util.as_utc(dt_end)
        )
        await asyncio.sleep(1)
        dt_start = dt_start.replace(month=1)
        costs_year = await self.site.get_cost_between_dates(
            dt_util.as_utc(dt_start), dt_util.as_utc(dt_end)
        )
        _LOGGER.debug("Cost refreshed %s %s %s", costs_day, costs_month, costs_year)
        self.notify_observers(costs_day, "day")
        self.notify_observers(costs_month, "month")
        self.notify_observers(costs_year, "year")

    def notify_observers(self, costs, name):
        """Send notification to observers."""
        if costs is not None:
            for cost in costs:
                charger_id = cost["chargerId"]
                if charger_id in self.observers:
                    self.observers[charger_id](name, cost)


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
        cost_data: CostData | None = None,
    ):
        """Initialize the product data."""
        self.product = product
        self.circuit: Circuit = circuit
        self.site: Site = site
        self.state = None
        self.config = None
        self.schedule = None
        self.weekly_schedule = None
        self.state_observers = {}
        self.config_observers = {}
        self.schedule_observers = {}
        self.weekly_schedule_observers = {}
        self.cost_observers = {}
        self.site_observers = {}
        self.circuit_observers = {}
        self.cost_data: CostData = cost_data
        if self.cost_data is not None:
            self.cost_data.register_for_update(self.product.id, self.cost_update)
        self.cost_day = {"totalEnergyUsage": 0, "totalCost": 0, "currencyId": ""}
        self.cost_month = {"totalEnergyUsage": 0, "totalCost": 0, "currencyId": ""}
        self.cost_year = {"totalEnergyUsage": 0, "totalCost": 0, "currencyId": ""}
        self.streamdata = streamdata
        self.poll_observations = poll_observations
        self.master = master
        self.firmware_auth_failure = None

    def register_for_update(self, name, entity):
        """Register a entity to watch changes."""
        _LOGGER.debug("Register for updates on %s with %s", name, entity)

        if "." in name:
            first, second = name.split(".")

            if first == "state":
                observers = self.state_observers
            elif first == "config":
                observers = self.config_observers
            elif first == "schedule":
                observers = self.schedule_observers
            elif first == "weekly_schedule":
                observers = self.weekly_schedule_observers
            elif first == "site":
                observers = self.site_observers
            elif first == "circuit":
                observers = self.circuit_observers
            elif first.startswith("cost"):
                observers = self.cost_observers
            else:
                _LOGGER.debug("No such data to watch %s", name)
                return

            if second not in observers:
                observers[second] = []
            observers[second].append(entity)

    def is_state_polled(self):
        """Check if state is polled."""
        return self.state is not None

    def is_config_polled(self):
        """Check if config is polled."""
        return self.config is not None

    def is_master(self):
        """Check if master."""
        return self.master

    async def async_firmware_refresh(self):
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
            self.set_state("latestFirmware", None)
            return

        self.set_state("latestFirmware", firmware["latestFirmware"])
        _LOGGER.debug(
            "Latest Firmware for %s: %s", self.product.id, firmware["latestFirmware"]
        )

    async def async_refresh(self, poll_observations=None):
        """Poll observations."""

        if poll_observations is None:
            poll_observations = self.poll_observations

        if self.state is None:
            self.state = await self.product.empty_state(raw=True)
            self.state["voltageNL1"] = None
            self.state["voltageNL2"] = None
            self.state["voltageNL3"] = None
            self.state["voltageL1L2"] = None
            self.state["voltageL1L3"] = None
            self.state["voltageL2L3"] = None
            self.state["internalTemperature"] = None
        if self.config is None:
            self.config = await self.product.empty_config(raw=True)

        _LOGGER.debug(
            "Polling state for %s using %s", self.product.id, poll_observations
        )
        observations = await self.product.get_observations(*poll_observations)
        for observation in observations["observations"]:
            data_id = observation["id"]
            value = observation["value"]
            data_type = observation["dataType"]

            await self.async_update_observation(data_type, data_id, value)

    async def async_schedules_interpret(self, data):
        """Interpret schedule data."""
        start_epoch = data.get("StartSchedule", 0)
        kind = data.get("ProfileKind")
        recurrency = data.get("RecurrencyKind")
        periods = data.get("Periods")

        self.schedule = ChargerSchedule({"isEnabled": False})
        self.weekly_schedule = ChargerWeeklySchedule({"isEnabled": False})

        # Weekly schedule
        if kind == "Recurring" and recurrency == "Weekly":
            self.set_weekly_schedule("isEnabled", True, False)
            for period in periods:
                time = dt_util.as_local(
                    dt_util.utc_from_timestamp(start_epoch + period[0])
                )
                day = time.weekday()
                if period[1] != 0:  # Start
                    saved_day = day
                    self.set_weekly_schedule(
                        weeklyScheduleStartDays[saved_day],
                        time.strftime("%H:%M"),
                        False,
                    )
                    self.set_weekly_schedule(
                        weeklyScheduleLimit[saved_day], period[1], False
                    )
                else:
                    self.set_weekly_schedule(
                        weeklyScheduleStopDays[saved_day], time.strftime("%H:%M"), False
                    )

        # Delayed or Daily schedule
        elif (kind == "Recurring" and recurrency == "Daily") or kind == "Absolute":
            self.set_schedule("isEnabled", True, False)
            self.set_schedule("repeat", kind == "Recurring", False)
            for period in periods:
                time = dt_util.as_local(
                    dt_util.utc_from_timestamp(start_epoch + period[0])
                )
                if period[1] != 0:  # Start
                    self.set_schedule("chargeStartTime", time.strftime("%H:%M"), False)
                    self.set_schedule("chargeLimit", period[1], False)
                else:
                    self.set_schedule("chargeStopTime", time.strftime("%H:%M"), False)

        # Make sure the entities update
        self.notify("isEnabled", self.weekly_schedule_observers)
        self.notify("isEnabled", self.schedule_observers)

    def cost_update(self, cost_type, cost_data):
        """Update callback for cost data."""
        if "day" in cost_type:
            self.cost_day = cost_data
        if "month" in cost_type:
            self.cost_month = cost_data
        if "year" in cost_type:
            self.cost_year = cost_data

        self.notify("totalCost", self.cost_observers)

    async def async_cost_refresh(self):
        """Ask for cost data update."""
        if self.cost_data is not None:
            self.cost_data.request_update(self.product.id)

    def check_latest_pulse(self):
        """Check if product has timed out."""
        if self.state is None:
            return

        now = dt_util.utcnow().replace(microsecond=0)
        try:
            elapsed = now - self.state["latestPulse"]
        except KeyError:
            return

        if elapsed.total_seconds() > OFFLINE_DELAY:
            if self.state["isOnline"] is True:
                self.set_state("isOnline", False)
                _LOGGER.debug("Product %s marked offline", self.product.id)

    def set_signalr_state(self, state):
        """Update status of SignalR stream."""
        if self.state is None:
            return

        self.set_state("signalRConnected", state)

    async def async_update_stream_data(self, data_type, data_id, value):
        """Update data with received data from SignalR stream."""
        if self.state is None:
            return False

        now = dt_util.utcnow().replace(microsecond=0)
        self.set_state("signalRConnected", True, False)
        self.set_state("latestPulse", now, False)
        self.set_state("isOnline", True)

        return await self.async_update_observation(data_type, data_id, value)

    async def async_update_observation(self, data_type, data_id, value):
        """Update observation."""

        try:
            name = self.streamdata(data_id).name
        except ValueError:
            # Unsupported data
            _LOGGER.debug(
                "Unsupported data id %s %s %s", self.product.id, data_id, value
            )
            return False

        _LOGGER.debug(
            "Observation update %s %s %s %s %s",
            self.product.id,
            data_id,
            name,
            value,
            data_type,
        )
        if "_" in name:
            try:
                first, second = name.split("_")
            except Exception as ex:  # pylint: disable=broad-except
                _LOGGER.print("Exception %s when splitting %s", ex, name)
                return False

            if first == "state":
                if self.state is None:
                    return False
                self.set_state(second, value)
                if second == "lifetimeEnergy":
                    await self.async_cost_refresh()
                return True
            elif first == "config":
                if self.config is None:
                    return False
                self.set_config(second, value)
                if second == "surplusCharging":
                    jsondata = json.loads(value)
                    self.set_config("surplusChargingMode", jsondata["mode"])
                    self.set_config(
                        "surplusChargingCurrent", jsondata["standbycurrent"]
                    )
                return True
            elif first == "schedule":
                _LOGGER.debug("Schedule update")
                if value == "":
                    value = "{}"
                await self.async_schedules_interpret(json.loads(value))
                return True
            else:
                _LOGGER.debug("Unknown update type: %s", first)

        return False

    def set_state(self, index, value, notify=True):
        """Update state and notify."""
        self.state[index] = value
        if notify:
            self.notify(index, self.state_observers)

    def set_config(self, index, value, notify=True):
        """Update config and notify."""
        self.config[index] = value
        if notify:
            self.notify(index, self.config_observers)

    def set_schedule(self, index, value, notify=True):
        """Update schedule and notify."""
        self.schedule[index] = value
        if notify:
            self.notify(index, self.schedule_observers)

    def set_weekly_schedule(self, index, value, notify=True):
        """Update weekly_schedule data and notify."""
        self.weekly_schedule[index] = value
        if notify:
            self.notify(index, self.weekly_schedule_observers)

    def notify(self, index, observers):
        """Notify any listeners that data has changed."""
        if index in observers:
            for observer in observers[index]:
                if observer.enabled:
                    observer.async_schedule_update_ha_state(True)

    def site_notify(self):
        """Notify any site listeners that data has changed."""
        for index in self.site_observers:
            for observer in self.site_observers[index]:
                if observer.enabled:
                    observer.async_schedule_update_ha_state(True)


class Controller:
    """Controller class orchestrating the data fetching and entitities."""

    _on_remove: list[CALLBACK_TYPE] | None = None

    def __init__(
        self,
        username: str,
        password: str,
        hass: HomeAssistant,
        config_entry: ConfigEntry,
    ):
        """Init the Controller class."""
        self.username = username
        self.password = password
        self.hass = hass
        self.entry = config_entry
        self.easee: Easee | None = None
        self.sites: list[Site] = []
        self.costs_data: list[CostData] = []
        self.circuits: list[Circuit] = []
        self.chargers: list[Charger] = []
        self.chargers_data: list[ProductData] = []
        self.equalizers: list[Equalizer] = []
        self.equalizers_data: list[ProductData] = []
        self.binary_sensor_entities = []
        self.button_entities = []
        self.light_entities = []
        self.switch_entities = []
        self.sensor_entities = []
        self.equalizer_sensor_entities = []
        self.equalizer_binary_sensor_entities = []
        self.equalizer_switch_entities = []
        self.diagnostics = {}
        self.monitored_sites = None
        self._init_count = 0

    def __del__(self):
        """Log deletion."""
        _LOGGER.debug("Controller deleted")

    @callback
    def async_on_remove(self, func: CALLBACK_TYPE) -> None:
        """Add a function to call when entity is removed or not added."""
        if self._on_remove is None:
            self._on_remove = []
        self._on_remove.append(func)

    def _call_on_remove_callbacks(self) -> None:
        """Call callbacks registered by async_on_remove."""
        if self._on_remove is None:
            return
        while self._on_remove:
            self._on_remove.pop()()

    async def async_cleanup(self):
        """Cleanup controller."""
        if "diagnostics" in self.hass.data[DOMAIN]:
            self.hass.data[DOMAIN].pop("diagnostics")

        if "sites_to_remove" in self.hass.data[DOMAIN]:
            self.hass.data[DOMAIN].pop("sites_to_remove")

        self._call_on_remove_callbacks()

        if self.easee is not None:
            for equalizer in self.equalizers:
                await self.easee.sr_unsubscribe(equalizer)
            for charger in self.chargers:
                await self.easee.sr_unsubscribe(charger)
            await self.easee.close()

        self.hass.data[DOMAIN].pop("controller")
        collect()

    async def async_initialize(self):
        """Initialize the session and get initial data."""
        client_session = aiohttp_client.async_get_clientsession(self.hass)
        ssl = get_default_context()
        self.easee = Easee(
            self.username, self.password, client_session, f"easee_hass_{VERSION}", ssl
        )

        try:
            async with asyncio.timeout(TIMEOUT):
                await self.easee.connect()
        except TimeoutError as err:
            _LOGGER.debug("Connection to easee login timed out")
            raise ConfigEntryNotReady from err
        except ServerFailureException as err:
            _LOGGER.debug("Easee server failure")
            raise ConfigEntryNotReady from err
        except TooManyRequestsException as err:
            _LOGGER.debug("Easee server too many requests")
            raise ConfigEntryNotReady from err
        except AuthorizationFailedException as err:
            _LOGGER.error("Authorization failed to Easee")
            raise ConfigEntryAuthFailed from err
        except BadRequestException as err:
            if err.args[0]["errorCode"] == 100:
                _LOGGER.error("Authorization (username/password) failed to Easee")
                raise ConfigEntryAuthFailed from err
            else:
                _LOGGER.error("Bad request %s", err)
        except Exception as err:  # pylint: disable=broad-except
            _LOGGER.exception("Unexpected error creating device: %s", err)
            return None

        try:
            self.sites: list[Site] = await self.easee.get_account_products()
            self.diagnostics["sites"] = self.sites

            self.monitored_sites = self.entry.options.get(
                CONF_MONITORED_SITES, [site.name for site in self.sites]
            )

            for site in self.sites:
                if site.name not in self.monitored_sites:
                    _LOGGER.debug("Found site (unmonitored): %s %s", site.id, site.name)
                else:
                    _LOGGER.debug("Found site (monitored): %s %s", site.id, site.name)
                    cost_data = CostData(site, period=60)
                    self.costs_data.append(cost_data)
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
                                    cost_data=cost_data,
                                )
                                self.chargers_data.append(charger_data)

            self.hass.data[DOMAIN]["diagnostics"] = self.diagnostics
            self._init_count = 0

            self._create_entitites()

        except Exception as err:
            _LOGGER.debug("Easee server failure %s", err)
            raise ConfigEntryNotReady from err

    async def async_stream_callback(self, idx, data_type, data_id, value):
        """Handle the he stream callback."""
        all_data = self.chargers_data + self.equalizers_data

        for data in all_data:
            if data.product.id == idx:
                await data.async_update_stream_data(data_type, data_id, value)

    async def async_setup_done(self, name):
        """Entities setup is done."""
        _LOGGER.debug("Entities %s setup done", name)
        self._init_count = self._init_count + 1

        if self._init_count >= len(PLATFORMS):
            await self.async_add_schedulers()

    async def async_add_schedulers(self):
        """Add schedules to update data."""
        # first update
        await self.async_refresh_sites_state()
        await self.async_refresh_equalizers_state()
        await asyncio.gather(
            *[charger.async_cost_refresh() for charger in self.chargers_data]
        )
        await asyncio.gather(
            *[charger.async_firmware_refresh() for charger in self.chargers_data]
        )
        await asyncio.gather(
            *[equalizer.async_firmware_refresh() for equalizer in self.equalizers_data]
        )
        for charger in self.chargers_data:
            charger.site_notify()

        # Add interval refresh for site state interval
        self.async_on_remove(
            async_track_time_interval(
                self.hass,
                self.async_refresh_sites_state,
                timedelta(seconds=SCAN_INTERVAL_STATE_SECONDS),
            )
        )

        # Add interval refresh for equalizer state interval
        self.async_on_remove(
            async_track_time_interval(
                self.hass,
                self.async_refresh_equalizers_state,
                timedelta(seconds=SCAN_INTERVAL_EQUALIZERS_SECONDS),
            )
        )

        # Add time pattern refresh some random time after midnight
        self.async_on_remove(
            async_track_time_change(
                self.hass,
                self.async_refresh_midnight,
                hour=0,
                minute=int(random() * 9),
                second=int(random() * 59),
            )
        )

        # Subscribe to updates from signalr stream
        for equalizer in self.equalizers:
            await self.easee.sr_subscribe(equalizer, self.async_stream_callback)
        for charger in self.chargers:
            await self.easee.sr_subscribe(charger, self.async_stream_callback)

    async def async_refresh_midnight(self, now=None):
        """Refresh the cost data."""
        _LOGGER.debug("Midnight refresh started")
        for charger in self.chargers_data:
            await charger.async_cost_refresh()
            await charger.async_firmware_refresh()

        for equalizer in self.equalizers_data:
            await equalizer.async_firmware_refresh()

    async def async_refresh_sites_state(self, now=None):
        """Get site state for all sites and updates the chargers state and config."""
        for charger_data in self.chargers_data:
            charger_data.set_signalr_state(self.easee.sr_is_connected())
            charger_data.check_latest_pulse()
            if charger_data.is_state_polled() and self.easee.sr_is_connected():
                continue

            await charger_data.async_refresh()
            charger_data.set_signalr_state(self.easee.sr_is_connected())

    async def async_refresh_equalizers_state(self, now=None):
        """Get equalizer state for all equalizers."""
        for equalizer_data in self.equalizers_data:
            equalizer_data.set_signalr_state(self.easee.sr_is_connected())
            equalizer_data.check_latest_pulse()
            if equalizer_data.is_state_polled() and self.easee.sr_is_connected():
                continue

            await equalizer_data.async_refresh()
            equalizer_data.set_signalr_state(self.easee.sr_is_connected())

    async def async_force_site_notify(self, product_id):
        """Send an update request to all entities watching site data."""
        for charger_data in self.chargers_data:
            if charger_data.product.id == product_id:
                charger_data.site_notify()

    def get_sites(self):
        """Get sites."""
        return self.sites

    def get_chargers(self):
        """Get chargers."""
        return self.chargers

    def get_equalizers(self):
        """Get equalizers."""
        return self.equalizers

    def check_circuit_current(
        self,
        circuit_id,
        current_p1,
        current_p2,
        current_p3,
        compare_str_p1,
        compare_str_p2,
        compare_str_p3,
    ):
        """Check circuit current."""
        if current_p2 is None:
            current_p2 = current_p1
        if current_p3 is None:
            current_p3 = current_p1

        for charger_data in self.chargers_data:
            if charger_data.circuit.id == circuit_id:
                try:
                    compare_p1 = charger_data.state[compare_str_p1]
                except KeyError:
                    try:
                        compare_p1 = charger_data.config[compare_str_p1]
                    except KeyError:
                        compare_p1 = None
                try:
                    compare_p2 = charger_data.state[compare_str_p2]
                except KeyError:
                    try:
                        compare_p2 = charger_data.config[compare_str_p2]
                    except KeyError:
                        compare_p2 = compare_p1
                try:
                    compare_p3 = charger_data.state[compare_str_p3]
                except KeyError:
                    try:
                        compare_p3 = charger_data.config[compare_str_p3]
                    except KeyError:
                        compare_p3 = compare_p1

                if (
                    compare_p1 != current_p1
                    or compare_p2 != current_p2
                    or compare_p3 != current_p3
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
        compare_str_p1,
        compare_str_p2,
        compare_str_p3,
    ):
        """Check charger current."""
        if current_p2 is None:
            current_p2 = current_p1
        if current_p3 is None:
            current_p3 = current_p1

        for charger_data in self.chargers_data:
            if charger_data.product.id == charger_id:
                try:
                    compare_p1 = charger_data.state[compare_str_p1]
                except KeyError:
                    try:
                        compare_p1 = charger_data.config[compare_str_p1]
                    except KeyError:
                        compare_p1 = None
                try:
                    compare_p2 = charger_data.state[compare_str_p2]
                except KeyError:
                    try:
                        compare_p2 = charger_data.config[compare_str_p2]
                    except KeyError:
                        compare_p2 = compare_p1
                try:
                    compare_p3 = charger_data.state[compare_str_p3]
                except KeyError:
                    try:
                        compare_p3 = charger_data.config[compare_str_p3]
                    except KeyError:
                        compare_p3 = compare_p1

                if (
                    compare_p1 != current_p1
                    or compare_p2 != current_p2
                    or compare_p3 != current_p3
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

    def get_button_entities(self):
        """Get button entities."""
        return self.button_entities

    def get_light_entities(self):
        """Get light entities."""
        return self.light_entities

    def get_sensor_entities(self):
        """Get sensor entities."""
        return self.sensor_entities + self.equalizer_sensor_entities

    def get_switch_entities(self):
        """Return switch_entities."""
        return self.switch_entities + self.equalizer_switch_entities

    def _create_entity(
        self,
        object_type,
        product_data,
        name,
        data,
    ):
        entity_type_name = ENTITY_TYPES[object_type]

        entity = entity_type_name(
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

        elif object_type == "button":
            self.button_entities.append(entity)

        elif object_type == "light":
            self.light_entities.append(entity)

        elif object_type == "eq_sensor":
            self.equalizer_sensor_entities.append(entity)

        elif object_type == "eq_binary_sensor":
            self.equalizer_binary_sensor_entities.append(entity)

        elif object_type == "eq_switch":
            self.equalizer_switch_entities.append(entity)

        return entity

    def _create_entitites(self):
        self.sensor_entities = []
        self.switch_entities = []
        self.binary_sensor_entities = []
        self.button_entities = []
        self.equalizer_sensor_entities = []
        self.equalizer_binary_sensor_entities = []
        self.equalizer_switch_entities = []

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
                    product_data=charger_data,
                    name=key,
                    data=data,
                )

        for equalizer_data in self.equalizers_data:
            for key, data in EASEE_EQ_ENTITIES.items():
                entity_type = data.get("type", "eq_sensor")

                self._create_entity(
                    entity_type,
                    product_data=equalizer_data,
                    name=key,
                    data=data,
                )
