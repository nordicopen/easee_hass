"""Easee charger switch."""

from homeassistant.components.switch import SwitchEntity
from homeassistant.const import CONF_MONITORED_CONDITIONS

from .entity import ChargerEntity, convert_units_funcs
from .const import DOMAIN, EASEE_ENTITIES
import logging

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass, entry, async_add_entities):
    """Setup switch platform."""
    config = hass.data[DOMAIN]["config"]
    chargers_data = hass.data[DOMAIN]["chargers_data"]
    monitored_conditions = config.options.get(CONF_MONITORED_CONDITIONS, ["status"])
    entities = []
    for charger_data in chargers_data._chargers:
        for key in monitored_conditions:
            if key in EASEE_ENTITIES:
                data = EASEE_ENTITIES[key]
                entity_type = data.get("type", "sensor")

                if entity_type == "switch":
                    _LOGGER.debug(
                        "Adding entity: %s (%s) for charger %s",
                        key,
                        entity_type,
                        charger_data.charger.name,
                    )
                    entities.append(
                        ChargerSwitch(
                            charger_data=charger_data,
                            name=key,
                            state_key=data["key"],
                            units=data["units"],
                            convert_units_func=convert_units_funcs.get(
                                data["convert_units_func"], None
                            ),
                            attrs_keys=data["attrs"],
                            icon=data["icon"],
                            state_func=data.get("state_func", None),
                            switch_func=data.get("switch_func", None),
                        )
                    )

    chargers_data._entities.extend(entities)
    async_add_entities(entities)


class ChargerSwitch(ChargerEntity, SwitchEntity):
    """Easee switch class."""

    async def async_turn_on(self, **kwargs):  # pylint: disable=unused-argument
        """Turn on the switch."""
        _LOGGER.debug("%s Switch turn on" % self._entity_name)
        function_call = getattr(self.charger_data.charger, self._switch_func)
        await function_call(True)
        await self.charger_data.async_refresh()
        await self.async_update()

    async def async_turn_off(self, **kwargs):  # pylint: disable=unused-argument
        """Turn off the switch."""
        _LOGGER.debug("%s Switch turn off" % self._entity_name)
        function_call = getattr(self.charger_data.charger, self._switch_func)
        await function_call(False)
        await self.charger_data.async_refresh()
        await self.async_update()

    @property
    def is_on(self):
        """Return true if the switch is on."""
        _LOGGER.debug("Getting state of %s" % self._entity_name)
        return self._state
