"""Config flow to configure Easee component."""
import logging
from typing import List, Optional

import voluptuous as vol
from aiohttp import ClientConnectionError
from homeassistant import config_entries
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import callback
from homeassistant.helpers import aiohttp_client
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.typing import ConfigType
from pyeasee import AuthorizationFailedException, Easee, Site

from .const import CONF_MONITORED_SITES, CUSTOM_UNITS, CUSTOM_UNITS_OPTIONS, DOMAIN

_LOGGER = logging.getLogger(__name__)


@config_entries.HANDLERS.register(DOMAIN)
class EaseeConfigFlow(config_entries.ConfigFlow):
    """Easee config flow."""

    VERSION = 2
    CONNECTION_CLASS = config_entries.CONN_CLASS_CLOUD_PUSH

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
        sites: List[Site] = controller.get_sites()
        sites_multi_select = {x["name"]: x["name"] for x in sites}
        default_sites = [x["name"] for x in sites]

        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema(
                {
                    vol.Optional(
                        CONF_MONITORED_SITES,
                        default=self.config_entry.options.get(
                            CONF_MONITORED_SITES, default_sites
                        ),
                    ): cv.multi_select(sites_multi_select),
                    vol.Optional(
                        CUSTOM_UNITS,
                        default=self.config_entry.options.get(CUSTOM_UNITS, []),
                    ): cv.multi_select(CUSTOM_UNITS_OPTIONS),
                }
            ),
            errors=errors,
        )

    async def _update_options(self):
        self.hass.data[DOMAIN]["sites_to_remove"] = [
            cond
            for cond in self.prev_options.get(CONF_MONITORED_SITES, {})
            if cond not in self.options[CONF_MONITORED_SITES]
        ]
        return self.async_create_entry(title="", data=self.options)
