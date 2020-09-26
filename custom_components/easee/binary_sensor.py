"""
Easee charger binary sensor.
Author: Niklas Fondberg<niklas.fondberg@gmail.com>
"""
from homeassistant.components.binary_sensor import BinarySensorEntity
from homeassistant.const import CONF_MONITORED_CONDITIONS
from .entity import ChargerEntity, convert_units_funcs
from .const import (
    DOMAIN,
    EASEE_ENTITIES,
)

import logging

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass, entry, async_add_entities):
    """Setup binary sensor platform."""
    config = hass.data[DOMAIN]["config"]
    chargers_data = hass.data[DOMAIN]["chargers_data"]
    monitored_conditions = config.options.get(CONF_MONITORED_CONDITIONS, ["status"])
    entities = []
    for charger_data in chargers_data._chargers:
        for key in monitored_conditions:
            data = EASEE_ENTITIES[key]
            entity_type = data.get("type", "sensor")

            if entity_type == "binary_sensor":
                _LOGGER.debug(
                    "Adding entity: %s (%s) for charger %s",
                    key,
                    entity_type,
                    charger_data.charger.name,
                )
                entities.append(
                    ChargerBinarySensor(
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
                    )
                )

    chargers_data._entities.extend(entities)
    async_add_entities(entities)


class ChargerBinarySensor(ChargerEntity, BinarySensorEntity):
    """Easee charger binary sensor class."""

    @property
    def is_on(self):
        """Return true if the binary sensor is on."""
        _LOGGER.debug("Getting state of %s" % self._entity_name)
        return self._state
