"""Config flow to configure Easee component."""

from __future__ import annotations

import logging
from typing import Any

from aiohttp import ClientConnectionError
import probatio
from pyeasee import AuthorizationFailedException, BadRequestException, Easee, Site

from homeassistant import config_entries
from homeassistant.config_entries import (
    ConfigEntry,
    ConfigFlowResult,
    OptionsFlow,
)
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import callback
from homeassistant.helpers import aiohttp_client, config_validation as cv

from .const import CONF_MONITORED_SITES, DOMAIN, VERSION

_LOGGER = logging.getLogger(__name__)


@config_entries.HANDLERS.register(DOMAIN)
class EaseeConfigFlow(config_entries.ConfigFlow):
    """Easee config flow."""

    VERSION = 3

    def __init__(self):
        """Set up the config flow."""

        self.sites = {}
        self.data = {}

    @staticmethod
    @callback
    def async_get_options_flow(config_entry) -> EaseeOptionsFlowHandler:
        """Get the options flow for this handler."""
        return EaseeOptionsFlowHandler(config_entry)

    async def async_step_reauth(self, entry_data) -> ConfigFlowResult:
        """Perform reauth upon an API authentication error."""
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Dialog that informs the user that reauth is required."""
        errors = {}
        reauth_entry = self._get_reauth_entry()
        if user_input is not None:
            new_input = reauth_entry.data | user_input
            try:
                client_session = aiohttp_client.async_get_clientsession(self.hass)
                easee = Easee(
                    reauth_entry.data[CONF_USERNAME],
                    user_input[CONF_PASSWORD],
                    client_session,
                    f"easee_hass_{VERSION}",
                )
                await easee.connect()
                self.hass.config_entries.async_update_entry(
                    reauth_entry, data=new_input
                )
                await self.hass.config_entries.async_reload(reauth_entry.entry_id)
                return self.async_abort(reason="reauth_successful")
            except (AuthorizationFailedException, BadRequestException):
                errors["base"] = "auth_failure"

            except ConnectionRefusedError:
                errors["base"] = "refused_failure"

            except ClientConnectionError:
                errors["base"] = "connection_failure"

        return self.async_show_form(
            step_id="reauth_confirm",
            data_schema=probatio.Schema(
                {probatio.Required(probatio.Secret(CONF_PASSWORD)): str}
            ),
            description_placeholders={"username": reauth_entry.data[CONF_USERNAME]},
            errors=errors,
        )

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle a flow start."""
        # Supporting a single account.
        entries = self.hass.config_entries.async_entries(DOMAIN)
        if entries:
            return self.async_abort(reason="already_setup")

        errors = {}
        _default_username = None

        if user_input is not None:
            username = user_input[CONF_USERNAME]
            password = user_input[CONF_PASSWORD]
            self.data = user_input

            try:
                client_session = aiohttp_client.async_get_clientsession(self.hass)
                easee = Easee(
                    username, password, client_session, f"easee_hass_{VERSION}"
                )
                # Check that login is possible
                await easee.connect()
                the_sites: list[Site] = await easee.get_account_products()
                self.sites = [site.name for site in the_sites]

                if len(self.sites) == 1:
                    return self.async_create_entry(
                        title=self.data[CONF_USERNAME],
                        data=self.data,
                        options={CONF_MONITORED_SITES: self.sites},
                    )
                if len(self.sites) > 1:
                    # Account has more than one site, select sites to add
                    return await self.async_step_sites()

                errors["base"] = "no_sites_in_account"
                _default_username = user_input[CONF_USERNAME]
                _LOGGER.debug("No sites in this account")

            except AuthorizationFailedException:
                errors["base"] = "auth_failure"
                _default_username = user_input[CONF_USERNAME]
                _LOGGER.debug("AuthorizationFailed")

            except ConnectionRefusedError:
                errors["base"] = "refused_failure"
                _LOGGER.debug("ConnectionRefusedError")

            except ClientConnectionError:
                errors["base"] = "connection_failure"
                _LOGGER.debug("ClientConnectionError")

        return self.async_show_form(
            step_id="user",
            data_schema=probatio.Schema(
                {
                    probatio.Required(CONF_USERNAME, default=_default_username): str,
                    probatio.Required(probatio.Secret(CONF_PASSWORD)): str,
                }
            ),
            errors=errors,
        )

    async def async_step_sites(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Select sites to monitor."""
        errors = {}
        if user_input is not None:
            if len(user_input[CONF_MONITORED_SITES]) > 0:
                return self.async_create_entry(
                    title=self.data[CONF_USERNAME], data=self.data, options=user_input
                )
            else:
                errors["base"] = "no_sites"

        return self.async_show_form(
            step_id="sites",
            data_schema=probatio.Schema(
                {
                    probatio.Optional(
                        CONF_MONITORED_SITES, default=self.sites
                    ): cv.multi_select(self.sites)
                }
            ),
            errors=errors,
        )

    async def async_step_import(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Occurs when an entry is setup through config."""
        return await self.async_step_user(user_input)


class EaseeOptionsFlowHandler(OptionsFlow):
    """Handle options."""

    def __init__(self, config_entry: ConfigEntry) -> None:
        """Initialize options flow."""
        self.options = dict(config_entry.options)
        self.prev_options = dict(config_entry.options)

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Manage the options."""

        errors = {}
        controller = self.hass.data[DOMAIN]["controller"]
        sites: list[Site] = controller.get_sites()
        sites_multi_select = {x["name"]: x["name"] for x in sites}
        default_sites = [x["name"] for x in sites]

        # Remove entries that are renamed or deleted in Easee cloud
        for x in self.config_entry.options.get(CONF_MONITORED_SITES, []):
            if x not in default_sites:
                self.config_entry.options[CONF_MONITORED_SITES].remove(x)

        if user_input is not None:
            if len(user_input[CONF_MONITORED_SITES]) == 0:
                errors["base"] = "no_sites"
            else:
                self.options.update(user_input)
                return await self._update_options(default_sites)

        return self.async_show_form(
            step_id="init",
            data_schema=probatio.Schema(
                {
                    probatio.Optional(
                        CONF_MONITORED_SITES,
                        default=self.config_entry.options.get(
                            CONF_MONITORED_SITES, default_sites
                        ),
                    ): cv.multi_select(sites_multi_select),
                }
            ),
            errors=errors,
        )

    async def _update_options(self, all_sites):
        self.hass.data[DOMAIN]["sites_to_remove"] = [
            cond
            for cond in self.prev_options.get(CONF_MONITORED_SITES, all_sites)
            if cond not in self.options[CONF_MONITORED_SITES]
        ]
        return self.async_create_entry(title="", data=self.options)
