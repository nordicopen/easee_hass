"""Setup wizard: connect one Easee charger to Home Assistant via local OCPP.

Steps: pick charger → check preconditions → confirm address → the wizard switches the
charger over through the Easee cloud and waits until it connects → done. If it does not
connect, the user can wait again, change the address, or roll back to cloud only.
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from datetime import datetime, timedelta
import secrets
import string
from typing import Any

import probatio

from homeassistant.config_entries import (
    SOURCE_RECONFIGURE,
    ConfigSubentryFlow,
    SubentryFlowResult,
)
from homeassistant.helpers.selector import (
    BooleanSelector,
    SelectOptionDict,
    SelectSelector,
    SelectSelectorConfig,
    TextSelector,
)

from ..const import DOMAIN
from .address import normalised_url, suggested_ocpp_url, url_problem
from .cloud_setup import (
    ChargerReadiness,
    EaseeOcppCloud,
    OcppCloudError,
    charger_readiness,
)
from .const import CONF_OCPP_PASSWORD, CONF_OCPP_URL, CONF_SERIAL, OCPP_PASSWORD_LENGTH
from .hub import OcppChargerConfig, OcppHub
from .server import HUB_DATA_KEY

type ChargerChoices = dict[str, str]

PASSWORD_ALPHABET = string.ascii_letters + string.digits
# In practice a charger needed about five minutes after the cloud change to connect.
CONNECT_TIMEOUT = timedelta(minutes=10)
CONNECT_POLL_INTERVAL = timedelta(seconds=2)
CONF_RESET_CIRCUIT_LIMIT = "reset_circuit_limit"
CHECK_PASSED = "✅"
CHECK_FAILED = "⚠️"
CHECK_UNKNOWN = "❔"


def generate_ocpp_password() -> str:
    """Random basic auth password within the Easee length limit."""
    return "".join(
        secrets.choice(PASSWORD_ALPHABET) for _ in range(OCPP_PASSWORD_LENGTH)
    )


def check_mark(passed: bool | None) -> str:
    """Symbol for one line of the precondition checklist."""
    if passed is None:
        return CHECK_UNKNOWN
    return CHECK_PASSED if passed else CHECK_FAILED


def readiness_placeholders(readiness: ChargerReadiness) -> dict[str, str]:
    """Checklist values shown in the precondition step."""
    firmware_known = readiness.firmware is not None
    return {
        "firmware_check": check_mark(
            readiness.firmware_supports_ocpp() if firmware_known else None
        ),
        "firmware": str(readiness.firmware) if firmware_known else "?",
        "wifi_check": check_mark(readiness.is_on_wifi()),
        "operator_check": check_mark(readiness.operator_is_easee()),
        "operator": readiness.operator_name or "?",
        "circuit_check": check_mark(not readiness.circuit_is_limited()),
    }


@dataclass(frozen=True)
class ConnectOutcome:
    """Result of switching the charger over and waiting for it."""

    connected: bool
    cloud_error: str | None = None


class OcppChargerSubentryFlow(ConfigSubentryFlow):
    """Adds one charger as OCPP charge point."""

    def __init__(self) -> None:
        """Start with nothing chosen."""
        self._serial = ""
        self._charger_name = ""
        self._password = generate_ocpp_password()
        self._url = ""
        self._address_error: str | None = None
        self._cloud_applied = False
        self._connect_task: asyncio.Task[ConnectOutcome] | None = None

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> SubentryFlowResult:
        """Let the user pick a charger that is not connected via OCPP yet."""
        if self._hub() is None:
            return self.async_abort(reason="integration_not_loaded")
        choices = self._unconfigured_chargers()
        if not choices:
            return self.async_abort(reason="no_unconfigured_chargers")
        if user_input is not None:
            self._serial = user_input[CONF_SERIAL]
            self._charger_name = choices[self._serial]
            return await self.async_step_prerequisites()
        return self.async_show_form(
            step_id="user",
            data_schema=probatio.Schema(
                {probatio.Required(CONF_SERIAL): charger_selector(choices)}
            ),
        )

    async def async_step_prerequisites(
        self, user_input: dict[str, Any] | None = None
    ) -> SubentryFlowResult:
        """Show what Easee requires and offer to lift a dynamic circuit limit."""
        product_data = self._product_data()
        readiness = charger_readiness(product_data.state, product_data.config)
        if readiness.firmware is not None and not readiness.firmware_supports_ocpp():
            return self.async_abort(
                reason="firmware_too_old",
                description_placeholders={"firmware": str(readiness.firmware)},
            )
        if user_input is not None:
            if user_input.get(CONF_RESET_CIRCUIT_LIMIT):
                await self._lift_circuit_limit(product_data, readiness)
            return await self.async_step_address()
        schema: dict[Any, Any] = {}
        if readiness.circuit_is_limited():
            schema[probatio.Optional(CONF_RESET_CIRCUIT_LIMIT, default=True)] = (
                BooleanSelector()
            )
        return self.async_show_form(
            step_id="prerequisites",
            data_schema=probatio.Schema(schema),
            description_placeholders={
                "charger": self._charger_name,
                **readiness_placeholders(readiness),
            },
        )

    async def async_step_address(
        self, user_input: dict[str, Any] | None = None
    ) -> SubentryFlowResult:
        """Confirm the URL the charger uses to reach Home Assistant."""
        errors: dict[str, str] = {}
        if self._address_error is not None:
            errors["base"] = self._address_error
            self._address_error = None
        if user_input is not None:
            url = normalised_url(user_input[CONF_OCPP_URL])
            problem = url_problem(url)
            if problem is None:
                self._url = url
                self._cloud_applied = False
                return await self.async_step_connect()
            errors[CONF_OCPP_URL] = problem
        default_url = self._url or await suggested_ocpp_url(self.hass)
        return self.async_show_form(
            step_id="address",
            data_schema=probatio.Schema(
                {probatio.Required(CONF_OCPP_URL, default=default_url): TextSelector()}
            ),
            description_placeholders={
                "charger": self._charger_name,
                "serial": self._serial,
            },
            errors=errors,
        )

    async def async_step_connect(
        self, user_input: dict[str, Any] | None = None
    ) -> SubentryFlowResult:
        """Switch the charger over via the Easee cloud and wait until it connects."""
        progress_was_shown = self._connect_task is not None
        if self._connect_task is None:
            self._connect_task = self.hass.async_create_task(
                self._switch_over_and_wait()
            )
        if not self._connect_task.done():
            return self.async_show_progress(
                step_id="connect",
                progress_action="wait_for_charger",
                progress_task=self._connect_task,
                description_placeholders={
                    "charger": self._charger_name,
                    "url": self._url,
                },
            )
        next_step = self._next_step_after(self._connect_task.result())
        self._connect_task = None
        if not progress_was_shown:
            # The task failed before any progress was shown (e.g. the cloud refused at once);
            # a progress-done result here would replay the address input forever.
            return await getattr(self, f"async_step_{next_step}")()
        return self.async_show_progress_done(next_step_id=next_step)

    def _next_step_after(self, outcome: ConnectOutcome) -> str:
        if outcome.connected:
            return "finish"
        if outcome.cloud_error is not None:
            self._address_error = outcome.cloud_error
            return "address"
        return "connection_failed"

    async def async_step_connection_failed(
        self, user_input: dict[str, Any] | None = None
    ) -> SubentryFlowResult:
        """Let the user decide what to do when the charger did not connect in time."""
        return self.async_show_menu(
            step_id="connection_failed",
            menu_options=["connect", "address", "rollback", "finish"],
            description_placeholders={"charger": self._charger_name, "url": self._url},
        )

    async def async_step_rollback(
        self, user_input: dict[str, Any] | None = None
    ) -> SubentryFlowResult:
        """Switch the charger back to cloud only."""
        try:
            await self._cloud().disable(self._serial)
        except OcppCloudError as error:
            return self.async_abort(reason=error.reason)
        return self.async_abort(reason="rolled_back")

    async def async_step_reconfigure(
        self, user_input: dict[str, Any] | None = None
    ) -> SubentryFlowResult:
        """Change the address of a configured charger; the password stays the same."""
        subentry = self._get_reconfigure_subentry()
        self._serial = subentry.data[CONF_SERIAL]
        self._charger_name = subentry.title.removeprefix("OCPP ")
        self._password = subentry.data[CONF_OCPP_PASSWORD]
        self._url = subentry.data.get(CONF_OCPP_URL, "")
        return await self.async_step_address()

    async def async_step_finish(
        self, user_input: dict[str, Any] | None = None
    ) -> SubentryFlowResult:
        """Store the charger; the integration reloads and serves it from now on."""
        if self.source == SOURCE_RECONFIGURE:
            return self.async_update_and_abort(
                self._get_entry(),
                self._get_reconfigure_subentry(),
                data_updates={CONF_OCPP_URL: self._url},
            )
        return self.async_create_entry(
            title=f"OCPP {self._charger_name}",
            data={
                CONF_SERIAL: self._serial,
                CONF_OCPP_PASSWORD: self._password,
                CONF_OCPP_URL: self._url,
            },
            unique_id=self._serial,
        )

    async def _switch_over_and_wait(self) -> ConnectOutcome:
        hub = self._hub()
        if hub is None:
            return ConnectOutcome(connected=False, cloud_error="integration_not_loaded")
        hub.expect_charger(OcppChargerConfig(self._serial, self._password))
        # When reconfiguring, the charger is still connected via the old address; wait for the new connection.
        previous_connection = hub.state(self._serial).connected_since
        if not self._cloud_applied:
            try:
                await self._cloud().enable(self._serial, self._url, self._password)
            except OcppCloudError as error:
                return ConnectOutcome(connected=False, cloud_error=error.reason)
            self._cloud_applied = True
        return ConnectOutcome(
            connected=await wait_for_connection(hub, self._serial, previous_connection)
        )

    async def _lift_circuit_limit(
        self, product_data: Any, readiness: ChargerReadiness
    ) -> None:
        maximum = readiness.lowest_circuit_maximum()
        if maximum is not None and product_data.circuit is not None:
            await product_data.circuit.set_dynamic_current(maximum)

    def _hub(self) -> OcppHub | None:
        hub: OcppHub | None = self.hass.data.get(HUB_DATA_KEY)
        return hub

    def _controller(self) -> Any:
        return self.hass.data[DOMAIN]["controller"]

    def _cloud(self) -> EaseeOcppCloud:
        return EaseeOcppCloud(self._controller().easee)

    def _product_data(self) -> Any:
        return next(
            data
            for data in self._controller().chargers_data
            if data.product.id == self._serial
        )

    def _unconfigured_chargers(self) -> ChargerChoices:
        configured = {
            subentry.unique_id for subentry in self._get_entry().subentries.values()
        }
        return {
            charger.id: f"{charger.name} ({charger.id})"
            for charger in self._controller().get_chargers()
            if charger.id not in configured
        }


async def wait_for_connection(
    hub: OcppHub, serial: str, previous_connection: datetime | None
) -> bool:
    """Wait until the charger has opened a websocket newer than previous_connection, at most CONNECT_TIMEOUT."""

    def has_new_connection() -> bool:
        state = hub.state(serial)
        return hub.is_connected(serial) and state.connected_since != previous_connection

    try:
        async with asyncio.timeout(CONNECT_TIMEOUT.total_seconds()):
            while not has_new_connection():
                await asyncio.sleep(CONNECT_POLL_INTERVAL.total_seconds())
    except TimeoutError:
        return False
    return True


def charger_selector(choices: ChargerChoices) -> SelectSelector:
    """Dropdown of chargers, showing name and serial."""
    options = [
        SelectOptionDict(value=serial, label=label) for serial, label in choices.items()
    ]
    return SelectSelector(SelectSelectorConfig(options=options))
