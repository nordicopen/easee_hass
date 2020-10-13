"""Config flow to configure Easee component."""
import logging
from typing import List, Optional

from easee import AuthorizationFailedException, Easee, Site
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.core import callback
from homeassistant.const import CONF_USERNAME, CONF_PASSWORD, CONF_MONITORED_CONDITIONS
from homeassistant.helpers.typing import ConfigType
from homeassistant.helpers import (
    aiohttp_client,
    config_validation as cv,
)


from .const import (
    DOMAIN,
    MEASURED_CONSUMPTION_DAYS,
    MEASURED_CONSUMPTION_OPTIONS,
    CUSTOM_UNITS,
    CUSTOM_UNITS_OPTIONS,
    EASEE_ENTITIES,
    CONF_MONITORED_SITES,
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
                errors["base"] = "connection_failure"

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
        if user_input is not None:
            self.options.update(user_input)
            return await self._update_options()

        constroller = self.hass.data[DOMAIN]["controller"]
        sensor_multi_select = {x: x for x in list(EASEE_ENTITIES)}
        sites: List[Site] = constroller.get_sites()
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
                            CONF_MONITORED_CONDITIONS, ["status"]
                        ),
                    ): cv.multi_select(sensor_multi_select),
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
        )

    async def _update_options(self):
        """Update config entry options."""
        to_remove = []
        for cond in self.prev_options[CONF_MONITORED_CONDITIONS]:
            if cond not in self.options[CONF_MONITORED_CONDITIONS]:
                to_remove.append(cond)
        self.hass.data[DOMAIN]["entities_to_remove"] = to_remove
        return self.async_create_entry(title="", data=self.options)
