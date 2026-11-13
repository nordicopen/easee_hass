"""Constants for the local OCPP central system."""

from datetime import timedelta
from typing import Final

OCPP_SUBPROTOCOL: Final = "ocpp1.6"
OCPP_VIEW_BASE_PATH: Final = "/api/easee/ocpp"
OCPP_VIEW_URL: Final = OCPP_VIEW_BASE_PATH + "/{serial}"

SUBENTRY_TYPE_OCPP_CHARGER: Final = "ocpp_charger"
CONF_SERIAL: Final = "serial"
CONF_OCPP_PASSWORD: Final = "ocpp_password"
CONF_OCPP_URL: Final = "ocpp_url"
CONF_ALLOWED_ID_TAGS: Final = "allowed_id_tags"

# unique_id = <serial>_ocpp_<key>; the marker keeps them apart from the cloud entities.
OCPP_UNIQUE_ID_MARKER: Final = "_ocpp_"

CONNECTOR_ID_CHARGE_POINT: Final = 0
CONNECTOR_ID_VEHICLE: Final = 1

HEARTBEAT_INTERVAL: Final = timedelta(minutes=5)
RESPONSE_TIMEOUT: Final = timedelta(seconds=30)
BOOTSTRAP_DELAY_AFTER_CONNECT: Final = timedelta(seconds=10)
WEBSOCKET_PING_INTERVAL: Final = timedelta(seconds=55)

METER_VALUES_SAMPLED_DATA: Final = (
    "Power.Active.Import,Current.Import,Voltage,Current.Offered,"
    "Energy.Active.Import.Register,Temperature"
)
# Easee rejects short intervals (30 s was the smallest accepted value in practice),
# so the bootstrap tries the preferred value first and falls back upwards.
METER_VALUE_SAMPLE_INTERVAL_CANDIDATES: Final = (10, 15, 30, 60)

# Hidden Easee keys that are not part of a GetConfiguration without key list.
EASEE_HIDDEN_CONFIGURATION_KEYS: Final = ("FreeCharging", "FreeChargingIdTag")

# The Easee cloud limits the basic auth password to 20 characters.
OCPP_PASSWORD_LENGTH: Final = 20

CHARGE_POINT_MAX_PROFILE_ID: Final = 1
CHARGE_POINT_MAX_PROFILE_STACK_LEVEL: Final = 0
TX_DEFAULT_PROFILE_ID: Final = 3
# Limit set by an external controller (e.g. a PV surplus service). It sits above the max
# current profile and expires on its own, so the charger falls back to the max current
# (e.g. 0 A) when the controller stops renewing it.
CONTROL_LIMIT_PROFILE_ID: Final = 2
CONTROL_LIMIT_STACK_LEVEL: Final = 1
TX_DEFAULT_PROFILE_STACK_LEVEL: Final = 0

SIGNAL_OCPP_STATE_UPDATED: Final = "easee_ocpp_state_updated_{serial}"
EVENT_OCPP_AUTHORIZE: Final = "easee_ocpp_authorize"
