"""Easee Charger constants."""
from pyeasee import ChargerStreamData, EqualizerStreamData

from homeassistant.components.binary_sensor import BinarySensorDeviceClass
from homeassistant.components.sensor import SensorDeviceClass, SensorStateClass
from homeassistant.const import (
    Platform,
    UnitOfElectricCurrent,
    UnitOfElectricPotential,
    UnitOfEnergy,
    UnitOfPower,
    UnitOfTemperature,
)
from homeassistant.helpers.entity import EntityCategory

DOMAIN = "easee"
TIMEOUT = 30
VERSION = "0.9.55"
MIN_HA_VERSION = "2023.4.0"
CONF_MONITORED_SITES = "monitored_sites"
MANUFACTURER = "Easee"
MODEL_EQUALIZER = "Equalizer"
MODEL_CHARGING_ROBOT = "Charging Robot"
PLATFORMS = [Platform.BINARY_SENSOR, Platform.SENSOR, Platform.SWITCH]
LISTENER_FN_CLOSE = "update_listener_close_fn"
EASEE_PRODUCT_CODES = {1: "Easee Home", 100: "Easee Charge", 2: "Charge Lite"}

chargerObservations = {
    ChargerStreamData.config_phaseMode.value,
    ChargerStreamData.config_authorizationRequired.value,
    ChargerStreamData.config_localNodeType.value,
    ChargerStreamData.config_localAuthorizationRequired.value,
    ChargerStreamData.config_ledStripBrightness.value,
    ChargerStreamData.config_wiFiSSID.value,
    ChargerStreamData.config_maxChargerCurrent.value,
    ChargerStreamData.config_circuitMaxCurrentP1.value,
    ChargerStreamData.config_circuitMaxCurrentP2.value,
    ChargerStreamData.config_circuitMaxCurrentP3.value,
    ChargerStreamData.config_isEnabled.value,
    ChargerStreamData.config_enableIdleCurrent.value,
    ChargerStreamData.state_reasonForNoCurrent.value,
    ChargerStreamData.state_lockCablePermanently.value,
    ChargerStreamData.state_smartCharging.value,
    ChargerStreamData.state_cableLocked.value,
    ChargerStreamData.state_chargerOpMode.value,
    ChargerStreamData.state_totalPower.value,
    ChargerStreamData.state_sessionEnergy.value,
    ChargerStreamData.state_energyPerHour.value,
    ChargerStreamData.state_wiFiRSSI.value,
    ChargerStreamData.state_cellRSSI.value,
    ChargerStreamData.state_localRSSI.value,
    ChargerStreamData.state_outputPhase.value,
    ChargerStreamData.state_dynamicCircuitCurrentP1.value,
    ChargerStreamData.state_dynamicCircuitCurrentP2.value,
    ChargerStreamData.state_dynamicCircuitCurrentP3.value,
    ChargerStreamData.state_chargerFirmware.value,
    ChargerStreamData.state_inCurrentT2.value,
    ChargerStreamData.state_inCurrentT3.value,
    ChargerStreamData.state_inCurrentT4.value,
    ChargerStreamData.state_inCurrentT5.value,
    ChargerStreamData.state_outputCurrent.value,
    ChargerStreamData.state_inVoltageT1T2.value,
    ChargerStreamData.state_inVoltageT1T3.value,
    ChargerStreamData.state_inVoltageT1T4.value,
    ChargerStreamData.state_inVoltageT1T5.value,
    ChargerStreamData.state_inVoltageT2T3.value,
    ChargerStreamData.state_inVoltageT2T4.value,
    ChargerStreamData.state_inVoltageT2T5.value,
    ChargerStreamData.state_inVoltageT3T4.value,
    ChargerStreamData.state_inVoltageT3T5.value,
    ChargerStreamData.state_inVoltageT4T5.value,
    ChargerStreamData.state_ledMode.value,
    ChargerStreamData.state_cableRating.value,
    ChargerStreamData.state_dynamicChargerCurrent.value,
    ChargerStreamData.state_circuitTotalAllocatedPhaseConductorCurrentL1.value,
    ChargerStreamData.state_circuitTotalAllocatedPhaseConductorCurrentL2.value,
    ChargerStreamData.state_circuitTotalAllocatedPhaseConductorCurrentL3.value,
    ChargerStreamData.state_circuitTotalPhaseConductorCurrentL1.value,
    ChargerStreamData.state_circuitTotalPhaseConductorCurrentL2.value,
    ChargerStreamData.state_circuitTotalPhaseConductorCurrentL3.value,
    ChargerStreamData.state_wiFiAPEnabled.value,
    ChargerStreamData.state_lifetimeEnergy.value,
    ChargerStreamData.state_offlineMaxCircuitCurrentP1.value,
    ChargerStreamData.state_offlineMaxCircuitCurrentP2.value,
    ChargerStreamData.state_offlineMaxCircuitCurrentP3.value,
    ChargerStreamData.state_eqAvailableCurrentP1.value,
    ChargerStreamData.state_eqAvailableCurrentP2.value,
    ChargerStreamData.state_eqAvailableCurrentP3.value,
    ChargerStreamData.state_tempMax.value,
    ChargerStreamData.schedule_chargingSchedule.value,
}
equalizerObservations = {
    EqualizerStreamData.state_currentL1.value,
    EqualizerStreamData.state_currentL2.value,
    EqualizerStreamData.state_currentL3.value,
    EqualizerStreamData.state_voltageNL1.value,
    EqualizerStreamData.state_voltageNL2.value,
    EqualizerStreamData.state_voltageNL3.value,
    EqualizerStreamData.state_voltageL1L2.value,
    EqualizerStreamData.state_voltageL1L3.value,
    EqualizerStreamData.state_voltageL2L3.value,
    EqualizerStreamData.state_activePowerImport.value,
    EqualizerStreamData.state_activePowerExport.value,
    EqualizerStreamData.state_reactivePowerImport.value,
    EqualizerStreamData.state_reactivePowerExport.value,
    EqualizerStreamData.state_cumulativeActivePowerImport.value,
    EqualizerStreamData.state_cumulativeActivePowerExport.value,
    EqualizerStreamData.state_cumulativeReactivePowerImport.value,
    EqualizerStreamData.state_cumulativeReactivePowerExport.value,
    EqualizerStreamData.state_clockAndDateMeter.value,
    EqualizerStreamData.state_rcpi.value,
    EqualizerStreamData.state_maxPowerImport.value,
    EqualizerStreamData.state_localRSSI.value,
    EqualizerStreamData.state_softwareRelease.value,
    EqualizerStreamData.state_ledMode.value,
    EqualizerStreamData.state_equalizedChargeCurrentL1.value,
    EqualizerStreamData.state_equalizedChargeCurrentL2.value,
    EqualizerStreamData.state_equalizedChargeCurrentL3.value,
    EqualizerStreamData.state_internalTemperature.value,
    EqualizerStreamData.config_ssid.value,
    EqualizerStreamData.config_equalizerID.value,
    EqualizerStreamData.config_masterBackPlateID.value,
    EqualizerStreamData.config_siteStructure.value,
    EqualizerStreamData.config_meterID.value,
    EqualizerStreamData.config_meterType.value,
    EqualizerStreamData.config_gridType.value,
    EqualizerStreamData.config_numPhases.value,
}

weeklyScheduleStartDays = {
    0: "MondayStartTime",
    1: "TuesdayStartTime",
    2: "WednesdayStartTime",
    3: "ThursdayStartTime",
    4: "FridayStartTime",
    5: "SaturdayStartTime",
    6: "SundayStartTime",
}

weeklyScheduleStopDays = {
    0: "MondayStopTime",
    1: "TuesdayStopTime",
    2: "WednesdayStopTime",
    3: "ThursdayStopTime",
    4: "FridayStopTime",
    5: "SaturdayStopTime",
    6: "SundayStopTime",
}

MANDATORY_EASEE_ENTITIES = {
    "status": {
        "key": "state.chargerOpMode",
        "attrs": [
            "config.phaseMode",
            "state.outputPhase",
            "state.ledMode",
            "state.cableRating",
            "config.authorizationRequired",
            "config.localNodeType",
            "config.localAuthorizationRequired",
            "config.ledStripBrightness",
            "site.id",
            "site.name",
            "site.siteKey",
            "site.ratedCurrent",
            "circuit.id",
            "circuit.ratedCurrent",
        ],
        "units": None,
        "convert_units_func": "map_charger_status",
        "device_class": None,
        # "device_class": "easee__status",
        "icon": "mdi:ev-station",
        "translation_key": "easee_status",
    },
}
OPTIONAL_EASEE_ENTITIES = {
    "smart_charging": {
        "type": "switch",
        "key": "state.smartCharging",
        "attrs": [],
        "units": None,
        "convert_units_func": None,
        "translation_key": "smart_charging",
        "device_class": None,
        "icon": "mdi:auto-fix",
        "switch_func": "smart_charging",
        "enabled_default": True,
        "entity_category": EntityCategory.CONFIG,
    },
    "cable_locked": {
        "type": "binary_sensor",
        "key": "state.cableLocked",
        "attrs": [],
        "units": None,
        "convert_units_func": None,
        "translation_key": "cable_locked",
        "device_class": BinarySensorDeviceClass.LOCK,
        "icon": None,
        "state_func": lambda state: not bool(state["cableLocked"]),
        "entity_category": EntityCategory.DIAGNOSTIC,
    },
    "cable_locked_permanently": {
        "type": "switch",
        "key": "state.lockCablePermanently",
        "attrs": [],
        "units": None,
        "convert_units_func": None,
        "translation_key": "cable_locked_permanently",
        "device_class": None,
        "icon": "mdi:lock",
        "switch_func": "lockCablePermanently",
        "enabled_default": True,
        "entity_category": EntityCategory.CONFIG,
    },
    "power": {
        "key": "state.totalPower",
        "attrs": [],
        "units": UnitOfPower.KILO_WATT,
        "convert_units_func": None,
        "device_class": SensorDeviceClass.POWER,
        "state_class": SensorStateClass.MEASUREMENT,
        "translation_key": "power",
        "suggested_display_precision": 1,
        "icon": None,
    },
    "session_energy": {
        "key": "state.sessionEnergy",
        "attrs": [],
        "units": UnitOfEnergy.KILO_WATT_HOUR,
        "convert_units_func": None,
        "suggested_display_precision": 1,
        "translation_key": "session_energy",
        "device_class": SensorDeviceClass.ENERGY,
        "icon": None,
        "enabled_default": True,
        "entity_category": EntityCategory.DIAGNOSTIC,
    },
    "lifetime_energy": {
        "key": "state.lifetimeEnergy",
        "attrs": [],
        "units": UnitOfEnergy.KILO_WATT_HOUR,
        "convert_units_func": None,
        "suggested_display_precision": 1,
        "translation_key": "lifetime_energy",
        "device_class": SensorDeviceClass.ENERGY,
        "state_class": SensorStateClass.TOTAL_INCREASING,
        "icon": "mdi:counter",
        "entity_category": EntityCategory.DIAGNOSTIC,
    },
    "energy_per_hour": {
        "key": "state.energyPerHour",
        "attrs": [],
        "units": UnitOfEnergy.KILO_WATT_HOUR,
        "convert_units_func": None,
        "suggested_display_precision": 1,
        "translation_key": "energy_per_hour",
        "device_class": SensorDeviceClass.ENERGY,
        "icon": None,
        "entity_category": EntityCategory.DIAGNOSTIC,
    },
    "cost_day": {
        "key": "cost_day.totalCost",
        "attrs": [
            "cost_day.totalCost",
            "cost_day.currencyId",
            "cost_day.totalEnergyUsage",
        ],
        "units": None,
        "convert_units_func": None,
        "suggested_display_precision": 2,
        "translation_key": "cost_day",
        "device_class": SensorDeviceClass.MONETARY,
        "icon": None,
        "enabled_default": True,
        "entity_category": EntityCategory.DIAGNOSTIC,
    },
    "cost_month": {
        "key": "cost_month.totalCost",
        "attrs": [
            "cost_month.totalCost",
            "cost_month.currencyId",
            "cost_month.totalEnergyUsage",
        ],
        "units": None,
        "convert_units_func": None,
        "suggested_display_precision": 2,
        "translation_key": "cost_month",
        "device_class": SensorDeviceClass.MONETARY,
        "icon": None,
        "enabled_default": True,
        "entity_category": EntityCategory.DIAGNOSTIC,
    },
    "cost_year": {
        "key": "cost_year.totalCost",
        "attrs": [
            "cost_year.totalCost",
            "cost_year.currencyId",
            "cost_year.totalEnergyUsage",
        ],
        "units": None,
        "convert_units_func": None,
        "suggested_display_precision": 2,
        "translation_key": "cost_year",
        "device_class": SensorDeviceClass.MONETARY,
        "icon": None,
        "enabled_default": True,
        "entity_category": EntityCategory.DIAGNOSTIC,
    },
    "online": {
        "type": "binary_sensor",
        "key": "state.isOnline",
        "attrs": [
            "state.signalRConnected",
            "state.latestPulse",
            "config.wiFiSSID",
            "state.wiFiAPEnabled",
            "state.wiFiRSSI",
            "state.cellRSSI",
            "state.localRSSI",
        ],
        "units": None,
        "convert_units_func": None,
        "translation_key": "online",
        "device_class": BinarySensorDeviceClass.CONNECTIVITY,
        "icon": None,
        "entity_category": EntityCategory.DIAGNOSTIC,
    },
    "output_limit": {
        "key": "state.outputCurrent",
        "attrs": [],
        "units": UnitOfElectricCurrent.AMPERE,
        "convert_units_func": None,
        "suggested_display_precision": 1,
        "translation_key": "output_limit",
        "device_class": SensorDeviceClass.CURRENT,
        "icon": None,
        "enabled_default": False,
        "entity_category": EntityCategory.DIAGNOSTIC,
    },
    "current": {
        "key": "state.inCurrentT2",
        "attrs": [
            "state.inCurrentT2",
            "state.inCurrentT3",
            "state.inCurrentT4",
            "state.inCurrentT5",
        ],
        "units": UnitOfElectricCurrent.AMPERE,
        "convert_units_func": "None",
        "suggested_display_precision": 1,
        "translation_key": "current",
        "device_class": SensorDeviceClass.CURRENT,
        "state_class": SensorStateClass.MEASUREMENT,
        "icon": None,
        "state_func": lambda state: float(
            max(
                state["inCurrentT2"],
                state["inCurrentT3"],
                state["inCurrentT4"],
                state["inCurrentT5"],
            )
        ),
        "enabled_default": False,
        "entity_category": EntityCategory.DIAGNOSTIC,
    },
    "circuit_current": {
        "key": "state.circuitTotalPhaseConductorCurrentL1",
        "attrs": [
            "circuit.id",
            "circuit.circuitPanelId",
            "circuit.panelName",
            "circuit.ratedCurrent",
            "state.circuitTotalAllocatedPhaseConductorCurrentL1",
            "state.circuitTotalAllocatedPhaseConductorCurrentL2",
            "state.circuitTotalAllocatedPhaseConductorCurrentL3",
            "state.circuitTotalPhaseConductorCurrentL1",
            "state.circuitTotalPhaseConductorCurrentL2",
            "state.circuitTotalPhaseConductorCurrentL3",
        ],
        "units": UnitOfElectricCurrent.AMPERE,
        "convert_units_func": None,
        "suggested_display_precision": 1,
        "translation_key": "circuit_current",
        "device_class": SensorDeviceClass.CURRENT,
        "icon": None,
        "state_func": lambda state: float(
            max(
                state["circuitTotalPhaseConductorCurrentL1"]
                if state["circuitTotalPhaseConductorCurrentL1"] is not None
                else 0.0,
                state["circuitTotalPhaseConductorCurrentL2"]
                if state["circuitTotalPhaseConductorCurrentL2"] is not None
                else 0.0,
                state["circuitTotalPhaseConductorCurrentL3"]
                if state["circuitTotalPhaseConductorCurrentL3"] is not None
                else 0.0,
            )
        ),
        "enabled_default": False,
        "only_master": True,
        "entity_category": EntityCategory.DIAGNOSTIC,
    },
    "equalizer_limit": {
        "key": "state.eqAvailableCurrentP1",
        "attrs": [
            "state.eqAvailableCurrentP1",
            "state.eqAvailableCurrentP2",
            "state.eqAvailableCurrentP3",
        ],
        "units": UnitOfElectricCurrent.AMPERE,
        "convert_units_func": None,
        "suggested_display_precision": 0,
        "translation_key": "equalizer_limit",
        "device_class": SensorDeviceClass.CURRENT,
        "icon": None,
        "state_func": lambda state: float(
            max(
                state["eqAvailableCurrentP1"],
                state["eqAvailableCurrentP2"],
                state["eqAvailableCurrentP3"],
            )
        ),
        "enabled_default": False,
        "entity_category": EntityCategory.DIAGNOSTIC,
    },
    "dynamic_circuit_limit": {
        "key": "state.dynamicCircuitCurrentP1",
        "attrs": [
            "circuit.id",
            "circuit.circuitPanelId",
            "circuit.panelName",
            "circuit.ratedCurrent",
            "state.dynamicCircuitCurrentP1",
            "state.dynamicCircuitCurrentP2",
            "state.dynamicCircuitCurrentP3",
        ],
        "units": UnitOfElectricCurrent.AMPERE,
        "convert_units_func": "round_0_dec",
        "translation_key": "dynamic_circuit_limit",
        "device_class": SensorDeviceClass.CURRENT,
        "icon": None,
        "state_func": lambda state: float(
            max(
                state["dynamicCircuitCurrentP1"],
                state["dynamicCircuitCurrentP2"],
                state["dynamicCircuitCurrentP3"],
            )
        ),
        "enabled_default": False,
        "entity_category": EntityCategory.DIAGNOSTIC,
    },
    "max_circuit_limit": {
        "key": "config.circuitMaxCurrentP1",
        "attrs": [
            "circuit.id",
            "circuit.circuitPanelId",
            "circuit.panelName",
            "circuit.ratedCurrent",
            "config.circuitMaxCurrentP1",
            "config.circuitMaxCurrentP2",
            "config.circuitMaxCurrentP3",
        ],
        "units": UnitOfElectricCurrent.AMPERE,
        "convert_units_func": "round_0_dec",
        "translation_key": "max_circuit_limit",
        "device_class": SensorDeviceClass.CURRENT,
        "icon": None,
        "state_func": lambda config: float(
            max(
                config["circuitMaxCurrentP1"],
                config["circuitMaxCurrentP2"],
                config["circuitMaxCurrentP3"],
            )
        ),
        "enabled_default": False,
        "entity_category": EntityCategory.DIAGNOSTIC,
    },
    "dynamic_charger_limit": {
        "key": "state.dynamicChargerCurrent",
        "attrs": [
            "state.dynamicChargerCurrent",
        ],
        "units": UnitOfElectricCurrent.AMPERE,
        "convert_units_func": "round_0_dec",
        "translation_key": "dynamic_charger_limit",
        "device_class": SensorDeviceClass.CURRENT,
        "icon": None,
        "enabled_default": False,
        "entity_category": EntityCategory.DIAGNOSTIC,
    },
    "offline_circuit_limit": {
        "key": "state.offlineMaxCircuitCurrentP1",
        "attrs": [
            "circuit.id",
            "circuit.circuitPanelId",
            "circuit.panelName",
            "circuit.ratedCurrent",
            "state.offlineMaxCircuitCurrentP1",
            "state.offlineMaxCircuitCurrentP2",
            "state.offlineMaxCircuitCurrentP3",
        ],
        "units": UnitOfElectricCurrent.AMPERE,
        "convert_units_func": None,
        "suggested_display_precision": 0,
        "translation_key": "offline_circuit_limit",
        "device_class": SensorDeviceClass.CURRENT,
        "icon": None,
        "state_func": lambda state: float(
            max(
                state["offlineMaxCircuitCurrentP1"],
                state["offlineMaxCircuitCurrentP2"],
                state["offlineMaxCircuitCurrentP3"],
            )
        ),
        "enabled_default": False,
        "entity_category": EntityCategory.DIAGNOSTIC,
    },
    "max_charger_limit": {
        "key": "config.maxChargerCurrent",
        "attrs": [
            "config.maxChargerCurrent",
        ],
        "units": UnitOfElectricCurrent.AMPERE,
        "convert_units_func": "round_0_dec",
        "translation_key": "max_charger_limit",
        "device_class": SensorDeviceClass.CURRENT,
        "icon": None,
        "enabled_default": False,
        "entity_category": EntityCategory.DIAGNOSTIC,
    },
    "voltage": {
        "key": "state.inVoltageT2T3",
        "attrs": [
            "state.inVoltageT1T2",
            "state.inVoltageT1T3",
            "state.inVoltageT1T4",
            "state.inVoltageT1T5",
            "state.inVoltageT2T3",
            "state.inVoltageT2T4",
            "state.inVoltageT2T5",
            "state.inVoltageT3T4",
            "state.inVoltageT3T5",
            "state.inVoltageT4T5",
        ],
        "units": UnitOfElectricPotential.VOLT,
        "convert_units_func": None,
        "suggested_display_precision": 0,
        "device_class": SensorDeviceClass.VOLTAGE,
        "translation_key": "voltage",
        "state_class": SensorStateClass.MEASUREMENT,
        "icon": None,
        "enabled_default": False,
        "entity_category": EntityCategory.DIAGNOSTIC,
    },
    "reason_for_no_current": {
        "key": "state.reasonForNoCurrent",
        "attrs": [],
        "units": None,
        "convert_units_func": "map_reason_no_current",
        "device_class": "easee__reason_no_current",
        "icon": "mdi:alert-circle",
        "enabled_default": False,
        "translation_key": "easee_reason_no_current",
    },
    "is_enabled": {
        "type": "switch",
        "key": "config.isEnabled",
        "attrs": [],
        "units": None,
        "convert_units_func": None,
        "device_class": None,
        "icon": "mdi:power-standby",
        "switch_func": "enable_charger",
        "translation_key": "is_enabled",
    },
    "enable_idle_current": {
        "type": "switch",
        "key": "config.enableIdleCurrent",
        "attrs": [],
        "units": None,
        "convert_units_func": None,
        "translation_key": "idle_current",
        "device_class": None,
        "icon": "mdi:current-ac",
        "switch_func": "enable_idle_current",
        "entity_category": EntityCategory.CONFIG,
    },
    "update_available": {
        "type": "binary_sensor",
        "key": "state.chargerFirmware",
        "attrs": [
            "state.chargerFirmware",
            "state.latestFirmware",
        ],
        "units": None,
        "convert_units_func": None,
        "translation_key": "update_available",
        "device_class": None,
        "icon": "mdi:file-download",
        "state_func": lambda state: (
            int(state["chargerFirmware"]) < int(state["latestFirmware"])
        )
        if state["latestFirmware"] is not None
        else None,
        "enabled_default": False,
        "entity_category": EntityCategory.DIAGNOSTIC,
    },
    "basic_schedule": {
        "type": "binary_sensor",
        "key": "schedule.isEnabled",
        "attrs": [
            "schedule.isEnabled",
            "schedule.chargeStartTime",
            "schedule.chargeStopTime",
            "schedule.repeat",
        ],
        "units": None,
        "convert_units_func": None,
        "device_class": None,
        "translation_key": "basic_schedule",
        "icon": "mdi:clock-check",
        "state_func": lambda schedule: bool(schedule.isEnabled) or False,
        "enabled_default": False,
        "entity_category": EntityCategory.DIAGNOSTIC,
    },
    "weekly_schedule": {
        "type": "binary_sensor",
        "key": "weekly_schedule.isEnabled",
        "attrs": [
            "weekly_schedule.isEnabled",
            "weekly_schedule.MondayStartTime",
            "weekly_schedule.MondayStopTime",
            "weekly_schedule.TuesdayStartTime",
            "weekly_schedule.TuesdayStopTime",
            "weekly_schedule.WednesdayStartTime",
            "weekly_schedule.WednesdayStopTime",
            "weekly_schedule.ThursdayStartTime",
            "weekly_schedule.ThursdayStopTime",
            "weekly_schedule.FridayStartTime",
            "weekly_schedule.FridayStopTime",
            "weekly_schedule.SaturdayStartTime",
            "weekly_schedule.SaturdayStopTime",
            "weekly_schedule.SundayStartTime",
            "weekly_schedule.SundayStopTime",
        ],
        "units": None,
        "convert_units_func": None,
        "translation_key": "weekly_schedule",
        "device_class": None,
        "icon": "mdi:clock-check",
        "state_func": lambda weekly_schedule: bool(weekly_schedule.isEnabled) or False,
        "enabled_default": False,
        "entity_category": EntityCategory.DIAGNOSTIC,
    },
    "cost_per_kwh": {
        "key": "site.costPerKWh",
        "attrs": [
            "site.costPerKWh",
            "site.costPerKwhExcludeVat",
            "site.vat",
            "site.costPerKwhExcludeVat",
            "site.currencyId",
        ],
        "units": None,
        "convert_units_func": None,
        "translation_key": "cost_per_kwh",
        "device_class": SensorDeviceClass.MONETARY,
        "icon": None,
        "enabled_default": False,
        "entity_category": EntityCategory.DIAGNOSTIC,
    },
    "temp_max": {
        "key": "state.tempMax",
        "attrs": [],
        "units": UnitOfTemperature.CELSIUS,
        "convert_units_func": None,
        "suggested_display_precision": 0,
        "translation_key": "internal_temperature",
        "device_class": SensorDeviceClass.TEMPERATURE,
        "state_class": SensorStateClass.MEASUREMENT,
        "icon": None,
        "enabled_default": True,
        "entity_category": EntityCategory.DIAGNOSTIC,
    },
}

EASEE_EQ_ENTITIES = {
    "online": {
        "type": "eq_binary_sensor",
        "key": "state.isOnline",
        "attrs": [
            "state.signalRConnected",
            "state.latestPulse",
            "state.clockAndDateMeter",
            "state.rcpi",
            "state.localRSSI",
            "state.softwareRelease",
            "state.latestFirmware",
        ],
        "units": None,
        "convert_units_func": None,
        "translation_key": "online",
        "device_class": BinarySensorDeviceClass.CONNECTIVITY,
        "icon": None,
    },
    "import_power": {
        "key": "state.activePowerImport",
        "attrs": [
            "state.maxPowerImport",
        ],
        "units": UnitOfPower.KILO_WATT,
        "convert_units_func": None,
        "suggested_display_precision": 1,
        "translation_key": "import_power",
        "device_class": SensorDeviceClass.POWER,
        "state_class": SensorStateClass.MEASUREMENT,
        "icon": None,
    },
    "import_reactive_power": {
        "key": "state.reactivePowerImport",
        "attrs": [],
        "units": UnitOfPower.KILO_WATT,
        "convert_units_func": None,
        "suggested_display_precision": 1,
        "translation_key": "import_reactive_power",
        # TODO
        # Note, at the time of writing REACTIVE_POWER does not
        # support kVAr, so we can not use it.
        "device_class": SensorDeviceClass.POWER,
        "state_class": SensorStateClass.MEASUREMENT,
        "icon": None,
    },
    "export_power": {
        "key": "state.activePowerExport",
        "attrs": [],
        "units": UnitOfPower.KILO_WATT,
        "convert_units_func": None,
        "suggested_display_precision": 1,
        "translation_key": "export_power",
        "device_class": SensorDeviceClass.POWER,
        "state_class": SensorStateClass.MEASUREMENT,
        "icon": None,
    },
    "export_reactive_power": {
        "key": "state.reactivePowerExport",
        "attrs": [],
        "units": UnitOfPower.KILO_WATT,
        "convert_units_func": None,
        "suggested_display_precision": 1,
        "translation_key": "export_reactive_power",
        # TODO
        # Note, at the time of writing REACTIVE_POWER does not
        # support kVAr, so we can not use it.
        "device_class": SensorDeviceClass.POWER,
        "state_class": SensorStateClass.MEASUREMENT,
        "icon": None,
    },
    "voltage": {
        "key": "state.voltageNL1",
        "attrs": [
            "state.voltageNL1",
            "state.voltageNL2",
            "state.voltageNL3",
            "state.voltageL1L2",
            "state.voltageL1L3",
            "state.voltageL2L3",
        ],
        "units": UnitOfElectricPotential.VOLT,
        "convert_units_func": None,
        "suggested_display_precision": 0,
        "translation_key": "voltage",
        "device_class": SensorDeviceClass.VOLTAGE,
        "state_class": SensorStateClass.MEASUREMENT,
        "icon": None,
        "state_func": lambda state: float(
            max(
                state["voltageNL1"] or 0.0,
                state["voltageNL2"] or 0.0,
                state["voltageNL3"] or 0.0,
                state["voltageL1L2"] or 0.0,
                state["voltageL1L3"] or 0.0,
                state["voltageL2L3"] or 0.0,
            )
        ),
        "enabled_default": False,
        "entity_category": EntityCategory.DIAGNOSTIC,
    },
    "current": {
        "key": "state.currentL1",
        "attrs": [
            "state.currentL1",
            "state.currentL2",
            "state.currentL3",
        ],
        "units": UnitOfElectricCurrent.AMPERE,
        "convert_units_func": None,
        "suggested_display_precision": 1,
        "translation_key": "current",
        "device_class": SensorDeviceClass.CURRENT,
        "state_class": SensorStateClass.MEASUREMENT,
        "icon": None,
        "state_func": lambda state: float(
            max(
                state["currentL1"],
                state["currentL2"],
                state["currentL3"],
            )
        ),
        "enabled_default": False,
        "entity_category": EntityCategory.DIAGNOSTIC,
    },
    "import_energy": {
        "key": "state.cumulativeActivePowerImport",
        "attrs": [],
        "units": UnitOfEnergy.KILO_WATT_HOUR,
        "convert_units_func": None,
        "suggested_display_precision": 1,
        "translation_key": "import_energy",
        "device_class": SensorDeviceClass.ENERGY,
        "state_class": SensorStateClass.TOTAL_INCREASING,
        "icon": None,
        "entity_category": EntityCategory.DIAGNOSTIC,
    },
    "import_reactive_energy": {
        "key": "state.cumulativeReactivePowerImport",
        "attrs": [],
        "units": UnitOfEnergy.KILO_WATT_HOUR,
        "convert_units_func": None,
        "suggested_display_precision": 1,
        "translation_key": "import_reactive_energy",
        # TODO
        # Note, at the time of writing there is no REACTIVE_ENERGY class
        "device_class": SensorDeviceClass.ENERGY,
        "state_class": SensorStateClass.TOTAL_INCREASING,
        "icon": None,
        "entity_category": EntityCategory.DIAGNOSTIC,
    },
    "export_energy": {
        "key": "state.cumulativeActivePowerExport",
        "attrs": [],
        "units": UnitOfEnergy.KILO_WATT_HOUR,
        "convert_units_func": None,
        "suggested_display_precision": 1,
        "translation_key": "export_energy",
        "device_class": SensorDeviceClass.ENERGY,
        "state_class": SensorStateClass.TOTAL_INCREASING,
        "icon": None,
        "entity_category": EntityCategory.DIAGNOSTIC,
    },
    "export_reactive_energy": {
        "key": "state.cumulativeReactivePowerExport",
        "attrs": [],
        "units": UnitOfEnergy.KILO_WATT_HOUR,
        "convert_units_func": None,
        "suggested_display_precision": 1,
        "translation_key": "export_reactive_energy",
        # TODO
        # Note, at the time of writing there is no REACTIVE_ENERGY class
        "device_class": SensorDeviceClass.ENERGY,
        "state_class": SensorStateClass.TOTAL_INCREASING,
        "icon": None,
        "entity_category": EntityCategory.DIAGNOSTIC,
    },
    "temp_max": {
        "key": "state.internalTemperature",
        "attrs": [],
        "units": UnitOfTemperature.CELSIUS,
        "convert_units_func": None,
        "suggested_display_precision": 0,
        "translation_key": "internal_temperature",
        "device_class": SensorDeviceClass.TEMPERATURE,
        "state_class": SensorStateClass.MEASUREMENT,
        "icon": None,
        "enabled_default": True,
        "entity_category": EntityCategory.DIAGNOSTIC,
    },
}

EASEE_STATUS = {
    1: "disconnected",
    2: "awaiting_start",
    3: "charging",
    4: "completed",
    5: "error",
    6: "ready_to_charge",
    7: "awaiting_authorization",
    8: "de_authorizing",
    100: "start_charging",
    101: "stop_charging",
    102: "offline",
    103: "awaiting_load_balancing",
    104: "awaiting_authorization",
    105: "awaiting_smart_start",
    106: "awaiting_scheduled_start",
    107: "authenticating",
    108: "paused_due_to_equalizer",
    109: "searching_for_master",
    157: "erratic_ev",
    158: "error_temperature_too_high",
    159: "error_dead_powerboard",
    160: "error_overcurrent",
    161: "error_pen_fault",
}

NT_MASTER = "master"
NT_EXTENDER = "extender"

NODE_TYPE_STATUS = {
    1: NT_MASTER,
    2: NT_EXTENDER,
}

PM_LOCKED_SINGLE = "locked_single"
PM_AUTO = "auto"
PM_LOCKED_THREE = "locked_three"

PHASE_MODE_STATUS = {
    1: PM_LOCKED_SINGLE,
    2: PM_AUTO,
    3: PM_LOCKED_THREE,
}

RNC_NONE = "none"
RNC_OK = "ok"
RNC_MAX_CIRCUIT_CURRENT_TOO_LOW = "max_circuit_current_too_low"
RNC_MAX_DYNAMIC_CIRCUIT_CURRENT_TOO_LOW = "max_dynamic_circuit_current_too_low"
RNC_MAX_DYNAMIC_OFFLINE_FALLBACK_CURRENT_TOO_LOW = (
    "max_dynamic_offline_fallback_circuit_current_too_low"
)
RNC_CIRCUIT_FUSE_TOO_LOW = "circuit_fuse_too_low"
RNC_WAITING_IN_QUEUE = "waiting_in_queue"
RNC_WAITING_IN_FULLY = "waiting_in_fully"
RNC_ILLEGAL_GRID_TYPE = "illegal_grid_type"
RNC_NO_CURRENT_REQUEST_RECEIVED = "no_current_request"
RNC_NOT_CONNECTED_TO_MASTER = "not_connected_to_master"
RNC_CURRENT_FROM_EQ_TOO_LOW = "eq_too_low_current"
RNC_PHASE_NOT_CONNECTED = "phase_not_connected"
RNC_LIMITED_BY_CIRCUIT_FUSE = "limited_by_circuit_fuse"
RNC_LIMITED_BY_CIRCUIT_MAX_LIMIT = "limited_by_circuit_max_limit"
RNC_LIMITED_BY_CIRCUIT_DYNAMIC_LIMIT = "limited_by_circuit_dynamic_limit"
RNC_LIMITED_BY_EQUALIZER = "limited_by_equalizer"
RNC_LIMITED_BY_LOAD_BALANCING = "limited_by_load_balancing"
RNC_LIMITED_BY_OFFLINE_SETTING = "limited_by_offline_setting"
RNC_NOT_REQUESTING = "not_requesting_current"
RNC_MAX_CHARGER_CURRENT_TOO_LOW = "max_charger_current_too_low"
RNC_MAX_DYNAMIC_CHARGER_CURRENT_TOO_LOW = "max_dynamic_charger_current_too_low"
RNC_CHARGER_DISABLED = "charger_disabled"
RNC_PENDING_SCHEDULE = "pending_schedule"
RNC_PENDING_AUTHORIZATION = "pending_authorization"
RNC_CHARGER_IN_ERROR_STATE = "charger_in_error_state"
RNC_ERRATIC_EV = "ev_behaving_erratic"
RNC_LIMITED_BY_CABLE_RATING = "limited_by_cable_rating"
RNC_LIMITED_BY_SCHEDULE = "limited_by_schedule"
RNC_LIMITED_BY_CHARGER_MAX_LIMIT = "limited_by_charger_max_limit"
RNC_LIMITED_BY_CHARGER_DYNAMIC_LIMIT = "limited_by_charger_dynamic_limit"
RNC_CAR_NOT_CHARGING = "car_not_charging"
RNC_LIMITED_BY_LOCAL_ADJUSTMENT = "limited_by_local_adjustment"
RNC_LIMITED_BY_CAR = "limited_by_car"
RNC_UNDEFINED = "undefined"

REASON_NO_CURRENT = {
    "none": RNC_NONE,
    0: RNC_OK,
    1: RNC_MAX_CIRCUIT_CURRENT_TOO_LOW,
    2: RNC_MAX_DYNAMIC_CIRCUIT_CURRENT_TOO_LOW,
    3: RNC_MAX_DYNAMIC_OFFLINE_FALLBACK_CURRENT_TOO_LOW,
    4: RNC_CIRCUIT_FUSE_TOO_LOW,
    5: RNC_WAITING_IN_QUEUE,
    6: RNC_WAITING_IN_FULLY,
    7: RNC_ILLEGAL_GRID_TYPE,
    8: RNC_NO_CURRENT_REQUEST_RECEIVED,
    9: RNC_NOT_CONNECTED_TO_MASTER,
    10: RNC_CURRENT_FROM_EQ_TOO_LOW,
    11: RNC_PHASE_NOT_CONNECTED,
    25: RNC_LIMITED_BY_CIRCUIT_FUSE,
    26: RNC_LIMITED_BY_CIRCUIT_MAX_LIMIT,
    27: RNC_LIMITED_BY_CIRCUIT_DYNAMIC_LIMIT,
    28: RNC_LIMITED_BY_EQUALIZER,
    29: RNC_LIMITED_BY_LOAD_BALANCING,
    30: RNC_LIMITED_BY_OFFLINE_SETTING,
    50: RNC_NOT_REQUESTING,
    51: RNC_MAX_CHARGER_CURRENT_TOO_LOW,
    52: RNC_MAX_DYNAMIC_CHARGER_CURRENT_TOO_LOW,
    53: RNC_CHARGER_DISABLED,
    54: RNC_PENDING_SCHEDULE,
    55: RNC_PENDING_AUTHORIZATION,
    56: RNC_CHARGER_IN_ERROR_STATE,
    57: RNC_ERRATIC_EV,
    75: RNC_LIMITED_BY_CABLE_RATING,
    76: RNC_LIMITED_BY_SCHEDULE,
    77: RNC_LIMITED_BY_CHARGER_MAX_LIMIT,
    78: RNC_LIMITED_BY_CHARGER_DYNAMIC_LIMIT,
    79: RNC_CAR_NOT_CHARGING,
    80: RNC_LIMITED_BY_LOCAL_ADJUSTMENT,
    81: RNC_LIMITED_BY_CAR,
    100: RNC_UNDEFINED,
}
