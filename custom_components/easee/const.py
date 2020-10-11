"""Easee Charger constants."""
from homeassistant.const import (
    POWER_KILO_WATT,
    POWER_WATT,
    ELECTRICAL_CURRENT_AMPERE,
    ENERGY_KILO_WATT_HOUR,
    ENERGY_WATT_HOUR,
    VOLT,
)

DOMAIN = "easee"
MEASURED_CONSUMPTION_DAYS = "measured_consumption_days"
VERSION = "0.9.18"
CONF_MONITORED_SITES = "monitored_sites"
CUSTOM_UNITS = "custom_units"
PLATFORMS = ("sensor", "switch", "binary_sensor")
LISTENER_FN_CLOSE = "update_listener_close_fn"
MEASURED_CONSUMPTION_OPTIONS = {
    "1": "1",
    "7": "7",
    "14": "14",
    "30": "30",
    "365": "365",
}
CUSTOM_UNITS_OPTIONS = {
    POWER_KILO_WATT: f"Power {POWER_KILO_WATT} to {POWER_WATT}",
    ENERGY_KILO_WATT_HOUR: f"Energy {ENERGY_KILO_WATT_HOUR} to {ENERGY_WATT_HOUR}",
}
CUSTOM_UNITS_TABLE = {
    POWER_KILO_WATT: POWER_WATT,
    ENERGY_KILO_WATT_HOUR: ENERGY_WATT_HOUR,
}
EASEE_ENTITIES = {
    "smart_charging": {
        "type": "switch",
        "key": "state.smartCharging",
        "attrs": [],
        "units": None,
        "convert_units_func": None,
        "icon": "mdi:auto-fix",
        "switch_func": "smart_charging",
    },
    "cable_locked_car": {
        "type": "binary_sensor",
        "key": "state.cableLocked",
        "attrs": [
            "state.lockCablePermanently",
            "state.cableLocked",
        ],
        "units": None,
        "convert_units_func": None,
        "icon": "mdi:lock",
    },
    "cable_permanently_locked_charger  ": {
        "type": "switch",
        "key": "state.lockCablePermanently",
        "attrs": [
            "state.lockCablePermanently",
            "state.cableLocked",
        ],
        "units": None,
        "convert_units_func": None,
        "icon": "mdi:lock",
        "switch_func": "lockCablePermanently",
    },
    "status": {
        "key": "state.chargerOpMode",
        "attrs": [
            "config.phaseMode",
            "state.outputPhase",
            "state.ledMode",
            "state.cableRating",
            "config.limitToSinglePhaseCharging",
            "config.localNodeType",
            "config.localAuthorizationRequired",
            "config.ledStripBrightness",
            "site.id",
            "site.name",
            "site.siteKey",
            "circuit.id",
            "circuit.ratedCurrent",
        ],
        "units": None,
        "convert_units_func": None,
        "icon": "mdi:ev-station",
    },
    "total_power": {
        "key": "state.totalPower",
        "attrs": [],
        "units": POWER_KILO_WATT,
        "convert_units_func": "round_2_dec",
        "icon": "mdi:flash",
    },
    "session_energy": {
        "key": "state.sessionEnergy",
        "attrs": [],
        "units": ENERGY_KILO_WATT_HOUR,
        "convert_units_func": "round_2_dec",
        "icon": "mdi:flash",
    },
    "energy_per_hour": {
        "key": "state.energyPerHour",
        "attrs": [],
        "units": ENERGY_KILO_WATT_HOUR,
        "convert_units_func": "round_2_dec",
        "icon": "mdi:flash",
    },
    "online": {
        "type": "binary_sensor",
        "key": "state.isOnline",
        "attrs": [
            "state.latestPulse",
            "config.wiFiSSID",
            "state.wiFiAPEnabled",
            "state.wiFiRSSI",
            "state.cellRSSI",
            "state.localRSSI",
        ],
        "units": None,
        "convert_units_func": None,
        "icon": "mdi:wifi",
    },
    "output_current": {
        "key": "state.outputCurrent",
        "attrs": [],
        "units": ELECTRICAL_CURRENT_AMPERE,
        "convert_units_func": "round_2_dec",
        "icon": "mdi:sine-wave",
    },
    "in_current": {
        "key": "state.inCurrentT2",
        "attrs": [
            "state.outputCurrent",
            "state.inCurrentT2",
            "state.inCurrentT3",
            "state.inCurrentT4",
            "state.inCurrentT5",
        ],
        "units": ELECTRICAL_CURRENT_AMPERE,
        "convert_units_func": "round_2_dec",
        "icon": "mdi:sine-wave",
        "state_func": lambda state: float(
            max(
                state["inCurrentT2"],
                state["inCurrentT3"],
                state["inCurrentT4"],
                state["inCurrentT5"],
            )
        ),
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
        "units": ELECTRICAL_CURRENT_AMPERE,
        "convert_units_func": "round_2_dec",
        "icon": "mdi:sine-wave",
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
    },
    "dynamic_circuit_current": {
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
        "units": ELECTRICAL_CURRENT_AMPERE,
        "convert_units_func": "round_2_dec",
        "icon": "mdi:sine-wave",
        "state_func": lambda state: float(
            max(
                state["dynamicCircuitCurrentP1"],
                state["dynamicCircuitCurrentP2"],
                state["dynamicCircuitCurrentP3"],
            )
        ),
    },
    "max_circuit_current": {
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
        "units": ELECTRICAL_CURRENT_AMPERE,
        "convert_units_func": "round_2_dec",
        "icon": "mdi:sine-wave",
        "state_func": lambda config: float(
            max(
                config["circuitMaxCurrentP1"],
                config["circuitMaxCurrentP2"],
                config["circuitMaxCurrentP3"],
            )
        ),
    },
    "dynamic_charger_current": {
        "key": "state.dynamicChargerCurrent",
        "attrs": [
            "state.dynamicChargerCurrent",
        ],
        "units": ELECTRICAL_CURRENT_AMPERE,
        "convert_units_func": "round_2_dec",
        "icon": "mdi:sine-wave",
    },
    "max_charger_current": {
        "key": "config.maxChargerCurrent",
        "attrs": [
            "config.maxChargerCurrent",
        ],
        "units": ELECTRICAL_CURRENT_AMPERE,
        "convert_units_func": "round_2_dec",
        "icon": "mdi:sine-wave",
    },
    "voltage": {
        "key": "state.voltage",
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
        "units": VOLT,
        "convert_units_func": "round_2_dec",
        "icon": "mdi:sine-wave",
    },
    "reason_for_no_current": {
        "key": "state.reasonForNoCurrent",
        "attrs": [
            "state.reasonForNoCurrent",
            "state.reasonForNoCurrent",
        ],
        "units": "",
        "convert_units_func": None,
        "icon": "mdi:alert-circle",
    },
    "is_enabled": {
        "type": "switch",
        "key": "config.isEnabled",
        "attrs": [],
        "units": None,
        "convert_units_func": None,
        "icon": "mdi:power-standby",
        "switch_func": "enable_charger",
    },
    "enable_idle_current": {
        "type": "switch",
        "key": "config.enableIdleCurrent",
        "attrs": [],
        "units": None,
        "convert_units_func": None,
        "icon": "mdi:current-dc",
        "switch_func": "enable_idle_current",
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
        "icon": "mdi:file-download",
        "state_func": lambda state: int(state["chargerFirmware"])
        < int(state["latestFirmware"]),
    },
    "basic_schedule": {
        "type": "binary_sensor",
        "key": "schedule.id",
        "attrs": [
            "schedule.id",
            "schedule.chargeStartTime",
            "schedule.chargeStopTime",
            "schedule.repeat",
        ],
        "units": None,
        "convert_units_func": None,
        "icon": "mdi:clock-check",
        "state_func": lambda schedule: bool(schedule) or False,
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
        "icon": "mdi:currency-usd",
    },
}
