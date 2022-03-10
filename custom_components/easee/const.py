"""Easee Charger constants."""
from homeassistant.components.binary_sensor import (
    DEVICE_CLASS_CONNECTIVITY,
    DEVICE_CLASS_LOCK,
)
from homeassistant.components.sensor import (
    STATE_CLASS_MEASUREMENT,
    STATE_CLASS_TOTAL_INCREASING,
)
from homeassistant.const import (
    DEVICE_CLASS_CURRENT,
    DEVICE_CLASS_ENERGY,
    DEVICE_CLASS_POWER,
    DEVICE_CLASS_VOLTAGE,
    ELECTRIC_CURRENT_AMPERE,
    ELECTRIC_POTENTIAL_VOLT,
    ENERGY_KILO_WATT_HOUR,
    ENERGY_WATT_HOUR,
    POWER_KILO_WATT,
    POWER_WATT,
)
from homeassistant.helpers.entity import EntityCategory

DOMAIN = "easee"
TIMEOUT = 30
VERSION = "0.9.41"
CONF_MONITORED_SITES = "monitored_sites"
CUSTOM_UNITS = "custom_units"
PLATFORMS = ("sensor", "switch", "binary_sensor")
LISTENER_FN_CLOSE = "update_listener_close_fn"
CUSTOM_UNITS_OPTIONS = {
    POWER_KILO_WATT: f"Power {POWER_KILO_WATT} to {POWER_WATT}",
    ENERGY_KILO_WATT_HOUR: f"Energy {ENERGY_KILO_WATT_HOUR} to {ENERGY_WATT_HOUR}",
}
CUSTOM_UNITS_TABLE = {
    POWER_KILO_WATT: POWER_WATT,
    ENERGY_KILO_WATT_HOUR: ENERGY_WATT_HOUR,
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
            "config.limitToSinglePhaseCharging",
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
        "device_class": "easee__status",
        "icon": "mdi:ev-station",
    },
}
OPTIONAL_EASEE_ENTITIES = {
    "smart_charging": {
        "type": "switch",
        "key": "state.smartCharging",
        "attrs": [],
        "units": None,
        "convert_units_func": None,
        "device_class": None,
        "icon": "mdi:auto-fix",
        "switch_func": "smart_charging",
        "enabled_default": True,
        "entity_category": EntityCategory.CONFIG,
    },
    "cable_locked": {
        "type": "binary_sensor",
        "key": "state.cableLocked",
        "attrs": [
            "state.lockCablePermanently",
            "state.cableLocked",
        ],
        "units": None,
        "convert_units_func": None,
        "device_class": DEVICE_CLASS_LOCK,
        "icon": None,
        "state_func": lambda state: not bool(state["cableLocked"]),
        "entity_category": EntityCategory.DIAGNOSTIC,
    },
    "cable_locked_permanently": {
        "type": "switch",
        "key": "state.lockCablePermanently",
        "attrs": [
            "state.lockCablePermanently",
            "state.cableLocked",
        ],
        "units": None,
        "convert_units_func": None,
        "device_class": None,
        "icon": "mdi:lock",
        "switch_func": "lockCablePermanently",
        "enabled_default": True,
        "entity_category": EntityCategory.CONFIG,
    },
    "power": {
        "key": "state.totalPower",
        "attrs": [],
        "units": POWER_KILO_WATT,
        "convert_units_func": "round_1_dec",
        "device_class": DEVICE_CLASS_POWER,
        "state_class": STATE_CLASS_MEASUREMENT,
        "icon": None,
    },
    "session_energy": {
        "key": "state.sessionEnergy",
        "attrs": [],
        "units": ENERGY_KILO_WATT_HOUR,
        "convert_units_func": "round_1_dec",
        "device_class": DEVICE_CLASS_ENERGY,
        "icon": None,
        "enabled_default": True,
        "entity_category": EntityCategory.DIAGNOSTIC,
    },
    "lifetime_energy": {
        "key": "state.lifetimeEnergy",
        "attrs": [],
        "units": ENERGY_KILO_WATT_HOUR,
        "convert_units_func": "round_1_dec",
        "device_class": DEVICE_CLASS_ENERGY,
        "state_class": STATE_CLASS_TOTAL_INCREASING,
        "icon": "mdi:counter",
        "entity_category": EntityCategory.DIAGNOSTIC,
    },
    "energy_per_hour": {
        "key": "state.energyPerHour",
        "attrs": [],
        "units": ENERGY_KILO_WATT_HOUR,
        "convert_units_func": "round_1_dec",
        "device_class": DEVICE_CLASS_ENERGY,
        "icon": None,
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
        "device_class": DEVICE_CLASS_CONNECTIVITY,
        "icon": None,
        "entity_category": EntityCategory.DIAGNOSTIC,
    },
    "output_limit": {
        "key": "state.outputCurrent",
        "attrs": [],
        "units": ELECTRIC_CURRENT_AMPERE,
        "convert_units_func": "round_1_dec",
        "device_class": DEVICE_CLASS_CURRENT,
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
        "units": ELECTRIC_CURRENT_AMPERE,
        "convert_units_func": "round_1_dec",
        "device_class": DEVICE_CLASS_CURRENT,
        "state_class": STATE_CLASS_MEASUREMENT,
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
        "units": ELECTRIC_CURRENT_AMPERE,
        "convert_units_func": "round_1_dec",
        "device_class": DEVICE_CLASS_CURRENT,
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
        "units": ELECTRIC_CURRENT_AMPERE,
        "convert_units_func": "round_0_dec",
        "device_class": DEVICE_CLASS_CURRENT,
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
        "units": ELECTRIC_CURRENT_AMPERE,
        "convert_units_func": "round_0_dec",
        "device_class": DEVICE_CLASS_CURRENT,
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
        "units": ELECTRIC_CURRENT_AMPERE,
        "convert_units_func": "round_0_dec",
        "device_class": DEVICE_CLASS_CURRENT,
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
        "units": ELECTRIC_CURRENT_AMPERE,
        "convert_units_func": "round_0_dec",
        "device_class": DEVICE_CLASS_CURRENT,
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
        "units": ELECTRIC_CURRENT_AMPERE,
        "convert_units_func": "round_0_dec",
        "device_class": DEVICE_CLASS_CURRENT,
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
        "units": ELECTRIC_POTENTIAL_VOLT,
        "convert_units_func": "round_0_dec",
        "device_class": DEVICE_CLASS_VOLTAGE,
        "state_class": STATE_CLASS_MEASUREMENT,
        "icon": None,
        "enabled_default": False,
        "entity_category": EntityCategory.DIAGNOSTIC,
    },
    "reason_for_no_current": {
        "key": "state.reasonForNoCurrent",
        "attrs": [],
        "units": "",
        "convert_units_func": "map_reason_no_current",
        "device_class": "easee__reason_no_current",
        "icon": "mdi:alert-circle",
        "enabled_default": False,
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
    },
    "enable_idle_current": {
        "type": "switch",
        "key": "config.enableIdleCurrent",
        "attrs": [],
        "units": None,
        "convert_units_func": None,
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
        "device_class": None,
        "icon": "mdi:file-download",
        "state_func": lambda state: int(state["chargerFirmware"])
        < int(state["latestFirmware"]),
        "enabled_default": False,
        "entity_category": EntityCategory.DIAGNOSTIC,
    },
    "basic_schedule": {
        "type": "binary_sensor",
        "key": "schedule.isEnabled",
        "attrs": [
            "schedule.id",
            "schedule.isEnabled",
            "schedule.chargeStartTime",
            "schedule.chargeStopTime",
            "schedule.repeat",
        ],
        "units": None,
        "convert_units_func": None,
        "device_class": None,
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
        "device_class": None,
        "icon": "mdi:currency-usd",
        "enabled_default": False,
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
        "device_class": DEVICE_CLASS_CONNECTIVITY,
        "icon": None,
    },
    "import_power": {
        "key": "state.activePowerImport",
        "attrs": [
            "state.activePowerImport",
            "state.reactivePowerImport",
            "state.maxPowerImport",
        ],
        "units": POWER_KILO_WATT,
        "convert_units_func": "round_1_dec",
        "device_class": DEVICE_CLASS_POWER,
        "state_class": STATE_CLASS_MEASUREMENT,
        "icon": None,
    },
    "export_power": {
        "key": "state.activePowerExport",
        "attrs": [
            "state.activePowerExport",
            "state.reactivePowerExport",
        ],
        "units": POWER_KILO_WATT,
        "convert_units_func": "round_1_dec",
        "device_class": DEVICE_CLASS_POWER,
        "state_class": STATE_CLASS_MEASUREMENT,
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
        "units": ELECTRIC_POTENTIAL_VOLT,
        "convert_units_func": "round_0_dec",
        "device_class": DEVICE_CLASS_VOLTAGE,
        "state_class": STATE_CLASS_MEASUREMENT,
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
        "units": ELECTRIC_CURRENT_AMPERE,
        "convert_units_func": "round_1_dec",
        "device_class": DEVICE_CLASS_CURRENT,
        "state_class": STATE_CLASS_MEASUREMENT,
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
        "attrs": [
            "state.cumulativeActivePowerImport",
            "state.cumulativeReactivePowerImport",
        ],
        "units": ENERGY_KILO_WATT_HOUR,
        "convert_units_func": "round_1_dec",
        "device_class": DEVICE_CLASS_ENERGY,
        "state_class": STATE_CLASS_TOTAL_INCREASING,
        "icon": None,
        "entity_category": EntityCategory.DIAGNOSTIC,
    },
    "export_energy": {
        "key": "state.cumulativeActivePowerExport",
        "attrs": [
            "state.cumulativeActivePowerExport",
            "state.cumulativeReactivePowerExport",
        ],
        "units": ENERGY_KILO_WATT_HOUR,
        "convert_units_func": "round_1_dec",
        "device_class": DEVICE_CLASS_ENERGY,
        "state_class": STATE_CLASS_TOTAL_INCREASING,
        "icon": None,
        "entity_category": EntityCategory.DIAGNOSTIC,
    },
}

EA_DISCONNECTED = "disconnected"
EA_AWAITING_START = "awaiting_start"
EA_CHARGING = "charging"
EA_COMPLETED = "completed"
EA_ERROR = "error"
EA_READY_TO_CHARGE = "ready_to_charge"

EASEE_STATUS = {
    1: EA_DISCONNECTED,
    2: EA_AWAITING_START,
    3: EA_CHARGING,
    4: EA_COMPLETED,
    5: EA_ERROR,
    6: EA_READY_TO_CHARGE,
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
RNC_NOT_REQUESTING = "not_requesting_current"
RNC_MAX_CHARGER_CURRENT_TOO_LOW = "max_charger_current_too_low"
RNC_MAX_DYNAMIC_CHARGER_CURRENT_TOO_LOW = "max_dynamic_charger_current_too_low"
RNC_CHARGER_DISABLED = "charger_disabled"
RNC_PENDING_SCHEDULE = "pending_schedule"
RNC_PENDING_AUTHORIZATION = "pending_authorization"
RNC_CHARGER_IN_ERROR_STATE = "charger_in_error_state"
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
    50: RNC_NOT_REQUESTING,
    51: RNC_MAX_CHARGER_CURRENT_TOO_LOW,
    52: RNC_MAX_DYNAMIC_CHARGER_CURRENT_TOO_LOW,
    53: RNC_CHARGER_DISABLED,
    54: RNC_PENDING_SCHEDULE,
    55: RNC_PENDING_AUTHORIZATION,
    56: RNC_CHARGER_IN_ERROR_STATE,
    100: RNC_UNDEFINED,
}
