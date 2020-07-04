import aiohttp
import asyncio
import logging
import datetime
import json
from typing import Any, Callable, Dict, List, Optional, Set, Union, cast
from enum import Enum

_LOGGER = logging.getLogger(__name__)
_LOGGER.setLevel(logging.DEBUG)


class ChargerState:
    """
     {'smartCharging': False, 'cableLocked': True, 'chargerOpMode': 3, 'totalPower': 0.7749999761581421, 'sessionEnergy': 4.746643543243408, 'energyPerHour': 3.0957324504852295, 'wiFiRSSI': -62, 'cellRSSI': -73, 'localRSSI': None, 'outputPhase': 30, 'dynamicCircuitCurrentP1': 40.0, 'dynamicCircuitCurrentP2': 40.0, 'dynamicCircuitCurrentP3': 40.0, 'latestPulse': '2020-07-03T13:42:26Z', 'chargerFirmware': 230, 'latestFirmware': 230, 'voltage': 240.99000549316406, 'chargerRAT': 1, 'lockCablePermanently': False, 'inCurrentT2': 3.677000045776367, 'inCurrentT3': 3.684999942779541, 'inCurrentT4': 0.013000000268220901, 'inCurrentT5': 0.012000000104308128, 'outputCurrent': 16.0, 'isOnline': True, 'inVoltageT1T2': 3.753999948501587, 'inVoltageT1T3': 239.31500244140625, 'inVoltageT1T4': 238.56900024414062, 'inVoltageT1T5': 236.94000244140625, 'inVoltageT2T3': 240.99000549316406, 'inVoltageT2T4': 240.72900390625, 'inVoltageT2T5': 233.27699279785156, 'inVoltageT3T4': 409.3590087890625, 'inVoltageT3T5': 418.8580017089844, 'inVoltageT4T5': 409.6099853515625, 'ledMode': 24, 'cableRating': 20000.0, 'dynamicChargerCurrent': 32.0, 'circuitTotalAllocatedPhaseConductorCurrentL1': None, 'circuitTotalAllocatedPhaseConductorCurrentL2': None, 'circuitTotalAllocatedPhaseConductorCurrentL3': None, 'circuitTotalPhaseConductorCurrentL1': 3.5290000438690186, 'circuitTotalPhaseConductorCurrentL2': 0.014000000432133675, 'circuitTotalPhaseConductorCurrentL3': 0.012000000104308128, 'reasonForNoCurrent': 0, 'wiFiAPEnabled': False}
    """

    STATUS = {
        1: "STANDBY",
        2: "PAUSED",
        3: "CHARGING",
        4: "READY_TO_CHARGE",
        5: "UNKNOWN",
        6: "CAR_CONNECTED",
    }

    def __init__(self, data):
        self.data = data
        self.status = ChargerState.STATUS[data["chargerOpMode"]]
        self.online = data["isOnline"]
        self.smart_charging = data["smartCharging"]
        self.cable_locked = data["cableLocked"]
        self.total_power = round(data["totalPower"] * 1000)
        self.session_energy = round(data["sessionEnergy"])
        self.energy_hour = round(data["energyPerHour"])


class ChargerConfig:
    """
    {'isEnabled': True, 'lockCablePermanently': False, 'authorizationRequired': False, 'remoteStartRequired': True, 'smartButtonEnabled': False, 'wiFiSSID': 'fondberg mesh 1', 'detectedPowerGridType': 1, 'offlineChargingMode': 0, 'circuitMaxCurrentP1': 16.0, 'circuitMaxCurrentP2': 16.0, 'circuitMaxCurrentP3': 16.0, 'enableIdleCurrent': False, 'limitToSinglePhaseCharging': None, 'phaseMode': 2, 'localNodeType': 1, 'localAuthorizationRequired': False, 'localRadioChannel': 4, 'localShortAddress': 0, 'localParentAddrOrNumOfNodes': 0, 'localPreAuthorizeEnabled': None, 'localAuthorizeOfflineEnabled': None, 'allowOfflineTxForUnknownId': None, 'maxChargerCurrent': 32.0, 'ledStripBrightness': None}
    """

    def __init__(self, data):
        self.data = data


class Charger:
    def __init__(self, id: str, name: str, session: Any):
        self.id: str = id
        self.name: str = name
        self.session = session
        self.state: ChargerState = None
        self.config: ChargerConfig = None

    async def async_update(self):
        res = await self.session.get(f"/api/chargers/{self.id}/state")
        state = await res.json()
        self.state = ChargerState(state)

        res = await self.session.get(f"/api/chargers/{self.id}/config")
        config = await res.json()
        self.config = ChargerConfig(config)

        _LOGGER.info("Charger:\n %s\n\nState:\n %s\n\nConfig: %s", self.name, state, config)

    def __str__(self):
        return f"{self.id} - {self.name} - {self.config}"


class EaseeSession:
    def __init__(self, username, password, session: aiohttp.ClientSession = None):
        self.username = username
        self.password = password
        _LOGGER.info("user: '%s', pass: '%s'", username, password)
        self.base = "https://api.easee.cloud"
        self.token = {}
        self.headers = {
            "Accept": "application/json",
            "Content-Type": "application/json;charset=UTF-8",
        }
        if session is None:
            self.session = aiohttp.ClientSession()
        else:
            self.session = session

    async def post(self, url, **kwargs):
        _LOGGER.debug("post: %s(%s)", url, kwargs)
        await self._verify_updated_token()
        return await self.session.post(f"{self.base}{url}", headers=self.headers, **kwargs)

    async def get(self, url, **kwargs):
        _LOGGER.debug("get: %s(%s)", url, kwargs)
        await self._verify_updated_token()
        return await self.session.get(f"{self.base}{url}", headers=self.headers, **kwargs)

    async def _verify_updated_token(self):
        if "accessToken" not in self.token:
            return
        accessToken = self.token["accessToken"]
        self.headers["Authorization"] = f"Bearer {accessToken}"
        self.token["expires"] < datetime.datetime.now()

    async def _handle_token_response(self, res):
        self.token = await res.json()
        _LOGGER.info("TOKEN: %s", self.token)
        expiresIn = int(self.token["expiresIn"])
        now = datetime.datetime.now()
        self.token["expires"] = now + datetime.timedelta(0, 86400)

    async def connect(self):
        """
        Gets initial token
        """
        data = {"userName": self.username, "password": self.password}
        _LOGGER.info("getting token with creds: %s", data)
        res = await self.post("/api/accounts/token", json=data)
        await self._handle_token_response(res)

    async def refresh_token(self):
        """
        Refresh token
        """
        data = {
            "accessToken": self.token["accessToken"],
            "refreshToken": self.token["refreshToken"],
        }

        res = await self.post("/api/accounts/refresh_token", json=data)
        await self._handle_token_response(res)

    async def close(self):
        if self.session:
            await self.session.close()
            self.session = None

    async def get_chargers(self) -> List[Charger]:
        res = await self.get("/api/chargers")
        records = await res.json()
        _LOGGER.debug("Chargers:  %s", records)
        return [Charger(k["id"], k["name"], self) for k in records]
