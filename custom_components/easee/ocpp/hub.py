"""Central system: keeps track of all chargers connected via OCPP."""

from __future__ import annotations

import asyncio
from collections.abc import Iterable
from dataclasses import dataclass
import hmac
import logging

from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.dispatcher import async_dispatcher_send
from homeassistant.helpers.storage import Store
from homeassistant.util import dt as dt_util

from .authorization import normalised_id_tag
from .bootstrap import ChargePointBootstrapper
from .charge_point import (
    CommandFailedError,
    EaseeChargePoint,
    IdTagAuthorizer,
    OcppConnection,
)
from .const import BOOTSTRAP_DELAY_AFTER_CONNECT, SIGNAL_OCPP_STATE_UPDATED
from .models import ChargePointState, IdTag, Serial
from .server import BasicCredentials, ConnectionClosedError

_LOGGER = logging.getLogger(__name__)

STORAGE_KEY = "easee_ocpp_limits"
STORAGE_VERSION = 1
# A fresh charger may charge with its full rating; HA lowers it only when asked to.
DEFAULT_MAX_CURRENT_AMPS = 32.0


class ChargerNotConnectedError(CommandFailedError):
    """A command was sent to a charger that is not connected."""


@dataclass(frozen=True)
class OcppChargerConfig:
    """Credentials of one charger, taken from its config subentry."""

    serial: Serial
    password: str


class IdTagWhitelist:
    """Allows exactly the given RFID cards; an empty list rejects every card."""

    def __init__(self, id_tags: Iterable[IdTag]) -> None:
        """Remember the allowed cards."""
        self._allowed = {normalised_id_tag(tag) for tag in id_tags if tag.strip()}

    def is_allowed(self, serial: Serial, id_tag: IdTag) -> bool:
        """Return True if the card is on the list."""
        return normalised_id_tag(id_tag) in self._allowed


def signal_state_updated(serial: Serial) -> str:
    """Dispatcher signal sent whenever the state of a charger changed."""
    return SIGNAL_OCPP_STATE_UPDATED.format(serial=serial)


class OcppHub:
    """Owns the state and the live connection of every OCPP charger."""

    def __init__(
        self,
        hass: HomeAssistant,
        chargers: Iterable[OcppChargerConfig],
        authorizer: IdTagAuthorizer,
    ) -> None:
        """Set up the hub for the configured chargers."""
        self._hass = hass
        self._configs = {config.serial: config for config in chargers}
        self.authorizer = authorizer
        started_at = dt_util.utcnow()
        self._states = {
            serial: ChargePointState(serial, disconnected_since=started_at)
            for serial in self._configs
        }
        self._charge_points: dict[Serial, EaseeChargePoint] = {}
        self._connections: dict[Serial, OcppConnection] = {}
        self._bootstrapped: dict[Serial, EaseeChargePoint] = {}
        self._bootstrap_tasks: dict[EaseeChargePoint, set[asyncio.Task[None]]] = {}
        self._bootstrap_runs: dict[EaseeChargePoint, asyncio.Task[None]] = {}
        self._connection_locks: dict[Serial, asyncio.Lock] = {}
        self._shutting_down = False
        self._max_current: dict[Serial, float] = {}
        self._store: Store[dict[Serial, float]] = Store(
            hass, STORAGE_VERSION, STORAGE_KEY
        )

    async def async_load(self) -> None:
        """Load the limits HA set before the last restart."""
        self._max_current = await self._store.async_load() or {}

    def expect_charger(self, config: OcppChargerConfig) -> None:
        """Accept a charger that is being set up and has no subentry yet."""
        self._configs[config.serial] = config
        self._states.setdefault(
            config.serial,
            ChargePointState(config.serial, disconnected_since=dt_util.utcnow()),
        )

    def serials(self) -> list[Serial]:
        """Return the serials of all configured chargers."""
        return list(self._configs)

    async def async_forget_charger(self, serial: Serial) -> None:
        """Revoke credentials and close the connection after a setup rollback."""
        self._configs.pop(serial, None)
        connection = self._connections.get(serial)
        if connection is not None:
            await connection.close()

    def config(self, serial: Serial) -> OcppChargerConfig:
        """Return the configuration of a charger."""
        return self._configs[serial]

    def knows(self, serial: Serial) -> bool:
        """Return True if the charger has an OCPP subentry."""
        return serial in self._configs

    def password_matches(
        self, serial: Serial, credentials: BasicCredentials | None
    ) -> bool:
        """Check basic auth: user must be the serial, password the one from the subentry."""
        if credentials is None:
            return False
        expected = self._configs[serial].password
        user_matches = credentials.login == serial
        password_matches = hmac.compare_digest(
            credentials.password.encode("utf-8"), expected.encode("utf-8")
        )
        return user_matches and password_matches

    def record_authentication_failure(self, serial: Serial) -> None:
        """Count a failed login; the charger's stored password does not match the subentry."""
        self._states[serial].authentication_failures += 1
        _LOGGER.warning("OCPP basic auth for %s failed", serial)

    def state(self, serial: Serial) -> ChargePointState:
        """Return the live state of a charger."""
        return self._states[serial]

    def is_connected(self, serial: Serial) -> bool:
        """Return True if the charger currently has a websocket open."""
        return serial in self._charge_points

    def charge_point(self, serial: Serial) -> EaseeChargePoint:
        """Return the connected charge point or raise ChargerNotConnectedError."""
        charge_point = self._charge_points.get(serial)
        if charge_point is None:
            raise ChargerNotConnectedError(f"{serial} is not connected via OCPP")
        return charge_point

    def max_current(self, serial: Serial) -> float:
        """Return the charger limit HA keeps in force."""
        return self._max_current.get(serial, DEFAULT_MAX_CURRENT_AMPS)

    async def async_set_max_current(self, serial: Serial, amps: float) -> None:
        """Send a new charger limit and keep it for reconnects."""
        await self.charge_point(serial).set_charge_point_max_current(amps)
        self._max_current[serial] = amps
        await self._store.async_save(self._max_current)
        self.notify(serial)

    async def async_refresh(self, serial: Serial) -> None:
        """Re-read status, meter values, limit and configuration."""
        charge_point = self.charge_point(serial)
        await ChargePointBootstrapper(charge_point, self.max_current(serial)).refresh()

    async def async_serve(self, serial: Serial, connection: OcppConnection) -> None:
        """Run one websocket connection until it closes."""
        # Closing a socket yields to other requests. Serialize replacement so two
        # simultaneous reconnects cannot leave an untracked connection alive.
        async with self._connection_locks.setdefault(serial, asyncio.Lock()):
            if self._shutting_down or not self.knows(serial):
                await connection.close()
                return
            await self._replace_previous_connection(serial)
            if self._shutting_down or not self.knows(serial):
                await connection.close()
                return
            charge_point = EaseeChargePoint(
                self._states[serial],
                connection,
                self.authorizer,
                on_state_changed=lambda: self.notify(serial),
                on_boot=lambda: self._start_bootstrap(serial, force=True),
            )
            self._charge_points[serial] = charge_point
            self._connections[serial] = connection
            self._mark_connected(serial)
            task = self._hass.async_create_background_task(
                self._bootstrap_after_delay(serial, charge_point),
                f"easee_ocpp_bootstrap_{serial}",
            )
            self._bootstrap_tasks[charge_point] = {task}
        try:
            await charge_point.start()
        except ConnectionClosedError as reason:
            _LOGGER.info("%s disconnected: %s", serial, reason)
        except Exception:
            # The ocpp library ends its message loop on any handler error; close cleanly so the charger reconnects.
            _LOGGER.exception(
                "%s: OCPP message loop failed, closing the connection", serial
            )
        finally:
            tasks = self._bootstrap_tasks.pop(charge_point, set())
            for task in tasks:
                task.cancel()
            self._bootstrap_runs.pop(charge_point, None)
            self._forget_if_current(serial, charge_point)
            await connection.close()
            await asyncio.gather(*tasks, return_exceptions=True)

    async def async_shutdown(self) -> None:
        """Close all connections (the chargers reconnect on their own)."""
        self._shutting_down = True
        tasks = [task for tasks in self._bootstrap_tasks.values() for task in tasks]
        for task in tasks:
            task.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)
        for connection in list(self._connections.values()):
            await connection.close()

    @callback
    def notify(self, serial: Serial) -> None:
        """Tell the entities of a charger to refresh."""
        async_dispatcher_send(self._hass, signal_state_updated(serial))

    async def _replace_previous_connection(self, serial: Serial) -> None:
        previous = self._connections.pop(serial, None)
        if previous is not None:
            _LOGGER.info("%s reconnected, closing the previous connection", serial)
            await previous.close()

    def _mark_connected(self, serial: Serial) -> None:
        state = self._states[serial]
        state.connected = True
        state.connected_since = dt_util.utcnow()
        state.disconnected_since = None
        state.authentication_failures = 0
        _LOGGER.info("%s connected via OCPP", serial)
        self.notify(serial)

    def _forget_if_current(
        self, serial: Serial, charge_point: EaseeChargePoint
    ) -> None:
        if self._charge_points.get(serial) is not charge_point:
            return
        del self._charge_points[serial]
        self._connections.pop(serial, None)
        self._bootstrapped.pop(serial, None)
        self._states[serial].connected = False
        self._states[serial].disconnected_since = dt_util.utcnow()
        self.notify(serial)

    async def _bootstrap_after_delay(
        self, serial: Serial, charge_point: EaseeChargePoint
    ) -> None:
        await asyncio.sleep(BOOTSTRAP_DELAY_AFTER_CONNECT.total_seconds())
        if self._charge_points.get(serial) is charge_point:
            self._start_bootstrap(serial, force=False)

    @callback
    def _start_bootstrap(self, serial: Serial, force: bool) -> None:
        """Bootstrap once per connection, and again after every real BootNotification."""
        charge_point = self._charge_points.get(serial)
        if charge_point is None or self._shutting_down:
            return
        running = self._bootstrap_runs.get(charge_point)
        if running is not None and not running.done():
            return
        already_done = self._bootstrapped.get(serial) is charge_point
        if already_done and not force:
            return
        self._bootstrapped[serial] = charge_point
        bootstrapper = ChargePointBootstrapper(charge_point, self.max_current(serial))
        task = self._hass.async_create_background_task(
            bootstrapper.run(), f"easee_ocpp_bootstrap_run_{serial}"
        )
        self._bootstrap_runs[charge_point] = task
        tasks = self._bootstrap_tasks[charge_point]
        tasks.add(task)
        task.add_done_callback(tasks.discard)
