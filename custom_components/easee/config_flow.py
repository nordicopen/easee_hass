"""Config flow to configure zone component."""
from typing import Optional
import logging

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.core import callback
from homeassistant.const import CONF_USERNAME, CONF_PASSWORD, CONF_MONITORED_CONDITIONS
from homeassistant.helpers.typing import ConfigType
from homeassistant.helpers import (
    aiohttp_client,
    config_validation as cv,
)

from easee import Easee
from .const import DOMAIN, MEASURED_CONSUMPTION_DAYS, EASEE_ENTITIES

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
                await easee.get_chargers()
                return self.async_create_entry(title=username, data=user_input)
            except Exception:
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

    async def async_step_init(self, user_input=None):
        """Manage the options."""
        return await self.async_step_options_1()

    async def async_step_options_1(self, user_input=None):
        """Manage the options."""
        if user_input is not None:
            self.options.update(user_input)
            return await self._update_options()

        sensor_multi_select = {x: x for x in list(EASEE_ENTITIES)}

        return self.async_show_form(
            step_id="options_1",
            data_schema=vol.Schema(
                {
                    vol.Optional(
                        CONF_MONITORED_CONDITIONS,
                        default=self.config_entry.options.get(
                            CONF_MONITORED_CONDITIONS, ["status"]
                        ),
                    ): cv.multi_select(sensor_multi_select),
                    vol.Optional(
                        MEASURED_CONSUMPTION_DAYS,
                        default=self.config_entry.options.get(
                            MEASURED_CONSUMPTION_DAYS, ["1"]
                        ),
                    ): cv.multi_select(
                        {"1": "1", "7": "7", "14": "14", "30": "30", "365": "365"}
                    ),
                }
            ),
        )

    async def _update_options(self):
        """Update config entry options."""
        return self.async_create_entry(title="", data=self.options)
