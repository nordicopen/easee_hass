"""Config flow to configure Easee component."""
import logging
from typing import List, Optional

from pyeasee import AuthorizationFailedException, Easee, Site
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.core import callback
from homeassistant.const import CONF_USERNAME, CONF_PASSWORD, CONF_MONITORED_CONDITIONS
from homeassistant.helpers.typing import ConfigType
from homeassistant.helpers import (
    aiohttp_client,
    config_validation as cv,
)

from aiohttp import ClientConnectionError


from .const import (
    DOMAIN,
    CONSUMPTION_DAYS_PREFIX,
    MEASURED_CONSUMPTION_DAYS,
    MEASURED_CONSUMPTION_OPTIONS,
    CUSTOM_UNITS,
    CUSTOM_UNITS_OPTIONS,
    OPTIONAL_EASEE_ENTITIES,
    MANDATORY_EASEE_ENTITIES,
    EASEE_EQ_ENTITIES,
    CONF_MONITORED_SITES,
    CONF_MONITORED_EQ_CONDITIONS,
)

_LOGGER = logging.getLogger(__name__)


@config_entries.HANDLERS.register(DOMAIN)
class EaseeConfigFlow(config_entries.ConfigFlow):
    """Easee config flow."""

    VERSION = 1
    CONNECTION_CLASS = config_entries.CONN_CLASS_CLOUD_POLL

    @staticmethod
    @callback
    def async_get_options_flow(config_entry):
        """Get the options flow for this handler."""
        return OptionsFlowHandler(config_entry)

    async def async_step_user(self, user_input: Optional[ConfigType] = None):
        """Handle a flow start."""
        # Supporting a single account.
        entries = self.hass.config_entries.async_entries(DOMAIN)
        if entries:
            return self.async_abort(reason="already_setup")

        errors = {}

        if user_input is not None:
            username = user_input[CONF_USERNAME]
            password = user_input[CONF_PASSWORD]

            try:
                client_session = aiohttp_client.async_get_clientsession(self.hass)
                easee = Easee(username, password, client_session)
                # Check that login is possible
                await easee.connect()
                return self.async_create_entry(title=username, data=user_input)

            except AuthorizationFailedException:
                errors["base"] = "auth_failure"
                _LOGGER.debug("AuthorizationFailed")

            except (ConnectionRefusedError):
                errors["base"] = "refused_failure"
                _LOGGER.debug("ConnectionRefusedError")

            except (ClientConnectionError):
                errors["base"] = "connection_failure"
                _LOGGER.debug("ClientConnectionError")

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {vol.Required(CONF_USERNAME): str, vol.Required(CONF_PASSWORD): str}
            ),
            errors=errors,
        )

    async def async_step_import(self, user_input: Optional[ConfigType] = None):
        """Occurs when an entry is setup through config."""
        return await self.async_step_user(user_input)


class OptionsFlowHandler(config_entries.OptionsFlow):
    """Handle options."""

    def __init__(self, config_entry):
        """Initialize options flow."""
        self.config_entry = config_entry
        self.options = dict(config_entry.options)
        self.prev_options = dict(config_entry.options)

    async def async_step_init(self, user_input=None):
        """Manage the options."""

        errors = {}
        if user_input is not None:
            if len(user_input[CONF_MONITORED_SITES]) == 0:
                errors["base"] = "no_sites"
            else:
                self.options.update(user_input)
                return await self._update_options()
        controller = self.hass.data[DOMAIN]["controller"]
        sensor_multi_select = {x: x for x in list(OPTIONAL_EASEE_ENTITIES)}
        sensor_eq_multi_select = {x: x for x in list(EASEE_EQ_ENTITIES)}
        sites: List[Site] = controller.get_sites()
        sites_multi_select = []
        for site in sites:
            sites_multi_select.append(site["name"])

        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema(
                {
                    vol.Optional(
                        CONF_MONITORED_SITES,
                        default=self.config_entry.options.get(
                            CONF_MONITORED_SITES, sites_multi_select
                        ),
                    ): cv.multi_select(sites_multi_select),
                    vol.Optional(
                        CONF_MONITORED_CONDITIONS,
                        default=self.config_entry.options.get(
                            CONF_MONITORED_CONDITIONS, []
                        ),
                    ): cv.multi_select(sensor_multi_select),
                    vol.Optional(
                        CONF_MONITORED_EQ_CONDITIONS,
                        default=self.config_entry.options.get(
                            CONF_MONITORED_EQ_CONDITIONS, ["status"]
                        ),
                    ): cv.multi_select(sensor_eq_multi_select),
                    vol.Optional(
                        MEASURED_CONSUMPTION_DAYS,
                        default=self.config_entry.options.get(
                            MEASURED_CONSUMPTION_DAYS, []
                        ),
                    ): cv.multi_select(MEASURED_CONSUMPTION_OPTIONS),
                    vol.Optional(
                        CUSTOM_UNITS,
                        default=self.config_entry.options.get(CUSTOM_UNITS, []),
                    ): cv.multi_select(CUSTOM_UNITS_OPTIONS),
                }
            ),
            errors=errors,
        )

    async def _update_options(self):
        for x in self.options[CONF_MONITORED_CONDITIONS]:
            if x in MANDATORY_EASEE_ENTITIES:
                del self.options[CONF_MONITORED_CONDITIONS][x]
        """Update config entry options."""
        self.hass.data[DOMAIN]["entities_to_remove"] = [cond for cond in self.prev_options.get(CONF_MONITORED_CONDITIONS, {})
            if cond not in self.options[CONF_MONITORED_CONDITIONS]]
        self.hass.data[DOMAIN]["eq_entities_to_remove"] = [cond for cond in self.prev_options.get(CONF_MONITORED_EQ_CONDITIONS, {})
            if cond not in self.options[CONF_MONITORED_EQ_CONDITIONS]]
        self.hass.data[DOMAIN]["sites_to_remove"] = [cond for cond in self.prev_options.get(CONF_MONITORED_SITES, {})
            if cond not in self.options[CONF_MONITORED_SITES]]
        self.hass.data[DOMAIN]["days_to_remove"] = [f"{CONSUMPTION_DAYS_PREFIX}{cond}" for cond in self.prev_options.get(MEASURED_CONSUMPTION_DAYS, {})
            if cond not in self.options[MEASURED_CONSUMPTION_DAYS]]
        _LOGGER.debug("Days_to_remove: %s", self.hass.data[DOMAIN]["days_to_remove"])
        return self.async_create_entry(title="", data=self.options)
