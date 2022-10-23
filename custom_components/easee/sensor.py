"""
Easee charger sensor
Author: Niklas Fondberg<niklas.fondberg@gmail.com>
"""

from datetime import timedelta
import logging

from homeassistant.components.sensor import SensorEntity
from homeassistant.helpers.entity import DeviceInfo

from .const import DOMAIN, MANUFACTURER, MODEL_EQUALIZER
from .entity import ChargerEntity

_LOGGER = logging.getLogger(__name__)

SCAN_INTERVAL = timedelta(minutes=15)


async def async_setup_entry(hass, entry, async_add_entities):
    """Setup sensor platform."""
    controller = hass.data[DOMAIN]["controller"]
    entities = controller.get_sensor_entities()
    async_add_entities(entities)
    controller.setup_done("sensor")


class ChargerSensor(ChargerEntity, SensorEntity):
    """Implementation of Easee charger sensor."""

    @property
    def native_value(self):
        """Return native value of sensor."""
        return self._state

    @property
    def native_unit_of_measurement(self):
        """Return native unit of measurement for sensor."""
        if self._state_key in ["site.costPerKWh", "cost_day.totalCost", "cost_month.totalCost", "cost_year.totalCost", ]:
            print(f"Data: {self.data.cost_day}")
            unit = self.data.cost_day.get("currencyId", "HEJ")
            print(f"Key: {self._state_key}  Unit: {unit}")
            return unit
        return self._units


class EqualizerSensor(ChargerEntity, SensorEntity):
    """Implementation of Easee equalizer sensor."""

    @property
    def native_value(self):
        """Return native value of sensor."""
        return self._state

    @property
    def device_info(self):
        """Return the device information."""
        return DeviceInfo(
            identifiers={(DOMAIN, self.data.product.id)},
            name=self.data.product.name,
            manufacturer=MANUFACTURER,
            model=MODEL_EQUALIZER,
            configuration_url=f"https://easee.cloud/mypage/products/{self.data.product.id}",
        )
