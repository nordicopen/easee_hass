"""
Easee charger sensor
Author: Niklas Fondberg<niklas.fondberg@gmail.com>
"""
import asyncio
from typing import Dict
from datetime import datetime, timedelta

from homeassistant.const import CONF_MONITORED_CONDITIONS
from homeassistant.helpers.entity import Entity

from .entity import ChargerEntity, convert_units_funcs, round_2_dec
from .const import DOMAIN, MEASURED_CONSUMPTION_DAYS, EASEE_ENTITIES

import logging


_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass, entry, async_add_entities):
    """Setup sensor platform."""
    config = hass.data[DOMAIN]["config"]
    chargers_data = hass.data[DOMAIN]["chargers_data"]
    monitored_conditions = config.options.get(CONF_MONITORED_CONDITIONS, ["status"])
    entities = []
    for charger_data in chargers_data._chargers:
        for key in monitored_conditions:
            data = EASEE_ENTITIES[key]
            entity_type = data.get("type", "sensor")

            if entity_type == "sensor":
                _LOGGER.debug(
                    "Adding entity: %s (%s) for charger %s",
                    key,
                    entity_type,
                    charger_data.charger.name,
                )
                entities.append(
                    ChargerSensor(
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

        monitored_days = config.options.get(MEASURED_CONSUMPTION_DAYS, [])
        for interval in monitored_days:
            _LOGGER.info("Will measure days: %s", interval)
            entities.append(
                ChargerConsumptionSensor(
                    charger_data.charger, f"consumption_days_{interval}", int(interval),
                )
            )

    chargers_data._entities.extend(entities)
    async_add_entities(entities)


class ChargerSensor(ChargerEntity):
    """Implementation of Easee charger sensor."""

    @property
    def state(self):
        """Return status."""
        return self._state


class ChargerConsumptionSensor(Entity):
    """Implementation of Easee charger sensor."""

    def __init__(self, charger, name, days):
        """Initialize the sensor."""
        self.charger = charger
        self._sensor_name = name
        self._days = days
        self._state = None

    @property
    def name(self):
        """Return the name of the sensor."""
        return f"{DOMAIN}_charger_{self.charger.id}_{self._sensor_name}"

    @property
    def unique_id(self) -> str:
        """Return a unique ID."""
        return f"{self.charger.id}_{self._sensor_name}"

    @property
    def device_info(self) -> Dict[str, any]:
        """Return the device information."""
        return {
            "identifiers": {(DOMAIN, self.charger.id)},
            "name": self.charger.name,
            "manufacturer": "Easee",
            "model": "Charging Robot",
        }

    @property
    def unit_of_measurement(self):
        """Return the unit of measurement of this entity, if any."""
        return "kWh"

    @property
    def available(self):
        """Return True if entity is available."""
        return self._state is not None

    @property
    def state(self):
        """Return online status."""
        return round_2_dec(self._state)

    @property
    def state_attributes(self):
        """Return the state attributes."""
        return {"name": self.charger.name, "id": self.charger.id}

    @property
    def icon(self):
        """Icon to use in the frontend, if any."""
        return "mdi:flash"

    async def async_update(self):
        """Get the latest data and update the state."""
        _LOGGER.debug(
            "ChargerConsumptionSensor async_update : %s %s",
            self.charger.name,
            self._sensor_name,
        )
        now = datetime.now()
        self._state = await self.charger.get_consumption_between_dates(
            now - timedelta(0, 86400 * self._days), now
        )
