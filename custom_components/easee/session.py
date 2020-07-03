import aiohttp
import asyncio
import logging

_LOGGER = logging.getLogger(__name__)


class EaseeSession:
    def __init__(self, username, password):
        self.username = username
        self.password = password
        self.base = "https://api.easee.cloud"
        self.token = {}
        self.headers = {
            "Accept": "application/json",
            "Content-Type": "application/json;charset=UTF-8",
        }

        self.session = aiohttp.ClientSession()

    async def post(self, url, **kwargs):
        _LOGGER.debug("post: %s(%s)", url, kwargs)
        return await self.session.post(
            f"{self.base}{url}", headers=self.headers, **kwargs
        )

    async def get(self, url, **kwargs):
        _LOGGER.debug("get: %s(%s)", url, kwargs)
        return await self.session.get(
            f"{self.base}{url}", headers=self.headers, **kwargs
        )

    async def get_initial_token(self):
        data = {"userName": self.username, "password": self.password}
        _LOGGER.info("getting token with creds: %s", data)
        res = await self.post("/api/accounts/token", json=data)
        token = await res.json()
        _LOGGER.debug("Token received %s", token)

        return token

    async def refresh_token(self):
        """
        /api/accounts/refresh_token
        {
            "accessToken": "string",
            "refreshToken": "string"
        }
        """
        pass

    async def connect(self):
        """
        TODO: implement caching of token and refresh
        token plus check if curr token is still valid
        """
        self.token = await self.get_initial_token()
        accessToken = self.token["accessToken"]
        self.headers["Authorization"] = f"Bearer {accessToken}"

    async def close(self):
        if self.session:
            await self.session.close()
            self.session = None


class ChargerState:
    """
     {'smartCharging': False, 'cableLocked': True, 'chargerOpMode': 3, 'totalPower': 0.7749999761581421, 'sessionEnergy': 4.746643543243408, 'energyPerHour': 3.0957324504852295, 'wiFiRSSI': -62, 'cellRSSI': -73, 'localRSSI': None, 'outputPhase': 30, 'dynamicCircuitCurrentP1': 40.0, 'dynamicCircuitCurrentP2': 40.0, 'dynamicCircuitCurrentP3': 40.0, 'latestPulse': '2020-07-03T13:42:26Z', 'chargerFirmware': 230, 'latestFirmware': 230, 'voltage': 240.99000549316406, 'chargerRAT': 1, 'lockCablePermanently': False, 'inCurrentT2': 3.677000045776367, 'inCurrentT3': 3.684999942779541, 'inCurrentT4': 0.013000000268220901, 'inCurrentT5': 0.012000000104308128, 'outputCurrent': 16.0, 'isOnline': True, 'inVoltageT1T2': 3.753999948501587, 'inVoltageT1T3': 239.31500244140625, 'inVoltageT1T4': 238.56900024414062, 'inVoltageT1T5': 236.94000244140625, 'inVoltageT2T3': 240.99000549316406, 'inVoltageT2T4': 240.72900390625, 'inVoltageT2T5': 233.27699279785156, 'inVoltageT3T4': 409.3590087890625, 'inVoltageT3T5': 418.8580017089844, 'inVoltageT4T5': 409.6099853515625, 'ledMode': 24, 'cableRating': 20000.0, 'dynamicChargerCurrent': 32.0, 'circuitTotalAllocatedPhaseConductorCurrentL1': None, 'circuitTotalAllocatedPhaseConductorCurrentL2': None, 'circuitTotalAllocatedPhaseConductorCurrentL3': None, 'circuitTotalPhaseConductorCurrentL1': 3.5290000438690186, 'circuitTotalPhaseConductorCurrentL2': 0.014000000432133675, 'circuitTotalPhaseConductorCurrentL3': 0.012000000104308128, 'reasonForNoCurrent': 0, 'wiFiAPEnabled': False}
    """

    def __init__(self, data):
        self.data = data


class ChargerConfig:
    """
    {'isEnabled': True, 'lockCablePermanently': False, 'authorizationRequired': False, 'remoteStartRequired': True, 'smartButtonEnabled': False, 'wiFiSSID': 'fondberg mesh 1', 'detectedPowerGridType': 1, 'offlineChargingMode': 0, 'circuitMaxCurrentP1': 16.0, 'circuitMaxCurrentP2': 16.0, 'circuitMaxCurrentP3': 16.0, 'enableIdleCurrent': False, 'limitToSinglePhaseCharging': None, 'phaseMode': 2, 'localNodeType': 1, 'localAuthorizationRequired': False, 'localRadioChannel': 4, 'localShortAddress': 0, 'localParentAddrOrNumOfNodes': 0, 'localPreAuthorizeEnabled': None, 'localAuthorizeOfflineEnabled': None, 'allowOfflineTxForUnknownId': None, 'maxChargerCurrent': 32.0, 'ledStripBrightness': None}
    """

    def __init__(self, data):
        self.data = data


class Charger:
    def __init__(self, id: str, name: str, state: ChargerState, config: ChargerConfig):
        self.id = id
        self.name = name
        self.state = state
        self.config = config

    @classmethod
    async def from_record(cls, session, record: dict):
        id = record["id"]
        res = await session.get(f"/api/chargers/{id}/state")
        state = await res.json()

        res = await session.get(f"/api/chargers/{id}/config")
        config = await res.json()
        _LOGGER.info(
            "Charger:\n %s\n\nState:\n %s\n\nConfig: %s", record, state, config
        )
        return cls(id, record["name"], ChargerState(state), ChargerConfig(config))


class Chargers:
    def __init__(self, session: EaseeSession):
        self.session = session

    async def get(self):
        res = await self.session.get("/api/chargers")
        records = await res.json()

        return await asyncio.gather(
            *[Charger.from_record(self.session, record) for record in records]
        )
