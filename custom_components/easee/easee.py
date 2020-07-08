import aiohttp
import asyncio
import logging
import datetime
import json
from typing import Any, Callable, Dict, List, Optional, Set, Union, cast
from enum import Enum

_LOGGER = logging.getLogger(__name__)

STATUS = {
    1: "STANDBY",
    2: "PAUSED",
    3: "CHARGING",
    4: "READY_TO_CHARGE",
    5: "UNKNOWN",
    6: "CAR_CONNECTED",
}

NODE_TYPE = {
    1: "Master",
    2: "Extender",
}

PHASE_MODE = {
    1: "Locked to single phase",
    2: "Auto",
    3: "Locked to three phase",
}


class Charger:
    def __init__(self, id: str, name: str, easee: Any):
        self.id: str = id
        self.name: str = name
        self.easee = easee
        self.state: {}
        self.config: {}

    async def get_consumption_between_dates(self, from_date, to_date):
        value = await (
            await self.easee.get(
                f"/api/sessions/charger/{self.id}/total/{from_date.isoformat()}/{to_date.isoformat()}"
            )
        ).text()
        return float(value)

    async def start(self):
        """Start charging session"""
        return await self.easee.post(f"/api/chargers/{self.id}/commands/start_charging")

    async def pause(self):
        """Pause charging session"""
        return await self.easee.post(f"/api/chargers/{self.id}/commands/pause_charging")

    async def resume(self):
        """Resume charging session"""
        return await self.easee.post(
            f"/api/chargers/{self.id}/commands/resume_charging"
        )

    async def stop(self):
        """Stop charging session"""
        return await self.easee.post(f"/api/chargers/{self.id}/commands/stop_charging")

    async def toggle(self):
        """Toggle charging session start/stop/pause/resume """
        return await self.easee.post(
            f"/api/chargers/{self.id}/commands/toggle_charging"
        )

    async def get_basic_charge_plan(self):
        """Get and return charger basic charge plan setting from cloud """
        return await self.easee.get(
            f"/api/chargers/{self.id}/commands/basic_charge_plan"
        )

    async def set_basic_charge_plan(
        self, id, chargeStartTime, chargeStopTime, repeat=True
    ):
        """Set and post charger basic charge plan setting to cloud """
        json = {
            "id": id,
            "chargeStartTime": chargeStartTime,
            "chargeStopTime": chargeStopTime,
            "repeat": repeat,
        }
        return await self.easee.post(
            f"/api/chargers/{self.id}/commands/basic_charge_plan", json=json
        )

    async def delete_basic_charge_plan(self):
        """Delete charger basic charge plan setting from cloud """
        return await self.easee.post(
            f"/api/chargers/{self.id}/commands/basic_charge_plan"
        )

    async def override_schedule(self):
        """Override scheduled charging and start charging"""
        return await self.easee.post(
            f"/api/chargers/{self.id}/commands/override_schedule"
        )

    async def smart_charging(self):
        """Set charger smart charging setting"""
        return await self.easee.post(f"/api/chargers/{self.id}/commands/smart_charging")

    async def reboot(self):
        """Reboot charger"""
        return await self.easee.post(f"/api/chargers/{self.id}/commands/reboot")

    async def update_firmware(self):
        """Update charger firmware"""
        return await self.easee.post(
            f"/api/chargers/{self.id}/commands/update_firmware"
        )

    async def async_update(self):
        state = await (await self.easee.get(f"/api/chargers/{self.id}/state")).json()
        self.state = {
            **state,
            "chargerOpMode": STATUS[state["chargerOpMode"]],
        }

        config = await (await self.easee.get(f"/api/chargers/{self.id}/config")).json()
        self.config = {
            **config,
            "localNodeType": NODE_TYPE[config["localNodeType"]],
            "phaseMode": PHASE_MODE[config["phaseMode"]],
        }

        _LOGGER.debug(
            "Charger:\n %s\n\nState:\n %s\n\nConfig: %s",
            self.name,
            self.state,
            self.config,
        )


async def raise_for_status(response):
    if 400 <= response.status:
        e = aiohttp.ClientResponseError(
            response.request_info,
            response.history,
            code=response.status,
            headers=response.headers,
        )

        if "json" in response.headers.get("CONTENT-TYPE", ""):
            data = await response.json()
            e.message = str(data)
        else:
            data = await response.text()
        _LOGGER.error("Error in request to Easee API: %s", data)
        raise Exception(data) from e


class Easee:
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
        _LOGGER.debug("post: %s (%s)", url, kwargs)
        await self._verify_updated_token()
        response = await self.session.post(
            f"{self.base}{url}", headers=self.headers, **kwargs
        )
        await raise_for_status(response)
        return response

    async def get(self, url, **kwargs):
        _LOGGER.debug("get: %s (%s)", url, kwargs)
        await self._verify_updated_token()
        response = await self.session.get(
            f"{self.base}{url}", headers=self.headers, **kwargs
        )
        await raise_for_status(response)
        return response

    async def _verify_updated_token(self):
        """
        Make sure there is a valid token
        """
        if "accessToken" not in self.token:
            await self._connect()
        accessToken = self.token["accessToken"]
        self.headers["Authorization"] = f"Bearer {accessToken}"
        if self.token["expires"] < datetime.datetime.now():
            self._refresh_token()

    async def _handle_token_response(self, res):
        """
        Handle the token request and set new datetime when it expires
        """
        self.token = await res.json()
        _LOGGER.info("TOKEN: %s", self.token)
        expiresIn = int(self.token["expiresIn"])
        now = datetime.datetime.now()
        self.token["expires"] = now + datetime.timedelta(0, 86400)

    async def _connect(self):
        """
        Gets initial token
        """
        data = {"userName": self.username, "password": self.password}
        _LOGGER.debug("getting token with creds: %s", data)
        response = await self.session.post(f"{self.base}/api/accounts/token", json=data)
        await raise_for_status(response)
        await self._handle_token_response(response)

    async def _refresh_token(self):
        """
        Refresh token
        """
        data = {
            "accessToken": self.token["accessToken"],
            "refreshToken": self.token["refreshToken"],
        }
        _LOGGER.debug("Refreshing access token")
        res = await self.post("/api/accounts/refresh_token", json=data)
        await self._handle_token_response(res)

    async def close(self):
        """
        Close the underlying aiohttp session
        """
        if self.session:
            await self.session.close()
            self.session = None

    async def get_chargers(self) -> List[Charger]:
        """
        Retrieve all chargers
        """
        records = await (await self.get("/api/chargers")).json()
        _LOGGER.debug("Chargers:  %s", records)
        return [Charger(k["id"], k["name"], self) for k in records]
