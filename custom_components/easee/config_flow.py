"""Config flow to configure zone component."""
from typing import Optional
import logging

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from homeassistant.helpers.typing import ConfigType
from easee import Easee

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)


@config_entries.HANDLERS.register(DOMAIN)
class EaseeConfigFlow(config_entries.ConfigFlow):
    """Easee config flow."""

    VERSION = 1
    CONNECTION_CLASS = config_entries.CONN_CLASS_CLOUD_POLL

    async def async_step_user(self, user_input: Optional[ConfigType] = None):
        """Handle a flow start."""
        # Supporting a single account.
        _LOGGER.info("async_step_user: %s", user_input)
        entries = self.hass.config_entries.async_entries(DOMAIN)
        if entries:
            _LOGGER.info("Already setup: %s", entries)
            return self.async_abort(reason="already_setup")

        errors = {}

        if user_input is not None:
            username = user_input[CONF_USERNAME]
            password = user_input[CONF_PASSWORD]

            try:
                easee = Easee(username, password)
                await easee.get_chargers()
                await easee.close()
                # await easee.login()
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
        _LOGGER.info("async_step_import: %s", user_input)
        return await self.async_step_user(user_input)
