"""Data coordinator for Olympia Electronics thermostats."""
import asyncio
import base64
import json
import logging
import time
from datetime import timedelta
from typing import Any, Optional

from aiohttp import ClientError, ClientTimeout
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed, HomeAssistantError
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

_LOGGER = logging.getLogger(__name__)

OLYMPIA_API_URL = "https://iot-api.olympia-electronics.gr/v1"
UPDATE_INTERVAL = 30
REQUEST_TIMEOUT = ClientTimeout(total=10)
TOKEN_REFRESH_BUFFER = 120


class CannotConnect(HomeAssistantError):
    """Error to indicate we cannot reach the Olympia Electronics cloud."""


class InvalidAuth(HomeAssistantError):
    """Error to indicate the credentials were rejected."""


def _parse_jwt_exp(token: str) -> Optional[float]:
    """Return the JWT ``exp`` claim by decoding the payload segment."""
    try:
        payload_b64 = token.split(".")[1]
        padding = "=" * (4 - len(payload_b64) % 4)
        payload = json.loads(base64.urlsafe_b64decode(payload_b64 + padding))
        return float(payload["exp"])
    except Exception as err:
        _LOGGER.warning("Could not read token expiry: %s", err)
        return None


async def async_login(session, email: str, password: str) -> tuple[str, Optional[float]]:
    """Log in to the Olympia cloud and return ``(jwt_token, expiry_epoch)``.

    Raises ``InvalidAuth`` for rejected credentials and ``CannotConnect`` for
    transport errors or unexpected responses. Used both by the config flow
    (standalone, no coordinator) and by the coordinator's token refresh.
    """
    try:
        async with session.post(
            f"{OLYMPIA_API_URL}/users/login/",
            json={"email": email, "password": password},
            timeout=REQUEST_TIMEOUT,
        ) as resp:
            body = await resp.text()
            if resp.status in (400, 401, 403):
                raise InvalidAuth(f"Login rejected: {resp.status}")
            if resp.status != 200:
                raise CannotConnect(f"Login failed: {resp.status} - {body}")
            try:
                data = await resp.json()
            except Exception as err:
                raise CannotConnect(f"Login response was not valid JSON: {body}") from err
    except (ClientError, asyncio.TimeoutError) as err:
        raise CannotConnect(f"Connection error during login: {err}") from err

    if data.get("non_field_errors"):
        raise InvalidAuth(f"Login error: {data['non_field_errors']}")
    token = data.get("token")
    if not token:
        raise InvalidAuth("Login response did not contain a token")
    return token, _parse_jwt_exp(token)


class OlympiaElectronicsCoordinator(DataUpdateCoordinator):
    """Coordinator for the Olympia Electronics cloud API."""

    def __init__(self, hass: HomeAssistant, email: str, password: str, config_entry=None):
        """Initialize coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            config_entry=config_entry,
            name="Olympia Electronics",
            update_interval=timedelta(seconds=UPDATE_INTERVAL),
        )
        self._email = email
        self._password = password
        self._session = None
        self._auth_token: Optional[str] = None
        self._token_expires_at: Optional[float] = None

    async def async_send_update(
        self,
        device_id: str,
        *,
        turn_on: Optional[bool] = None,
        boiler_on: Optional[bool] = None,
        setpoint: Optional[float] = None,
    ) -> None:
        """Push settings to a device, merging unspecified fields with the last
        known state so stale entity-held values are never sent.

        Raises HomeAssistantError if the update fails, so the calling service
        surfaces the error and Home Assistant reverts the optimistic state.
        """
        device = (self.data or {}).get(device_id, {})
        status, setting = device.get("status", {}), device.get("setting", {})

        if turn_on is None:
            turn_on = status.get("is_on", False)
        if boiler_on is None:
            boiler_on = status.get("boiler_on", False)
        if setpoint is None:
            setpoint = setting.get("setpoint", status.get("setpoint", 20.0))

        try:
            setpoint = round(float(setpoint), 1)
        except (TypeError, ValueError) as err:
            _LOGGER.error("Invalid setpoint for device %s: %s", device_id, setpoint)
            raise HomeAssistantError(
                f"Invalid setpoint for {device_id}: {setpoint}"
            ) from err

        payload = {
            "turn_on": "true" if turn_on else "false",
            "boiler_on": "true" if boiler_on else "false",
            "setpoint": str(setpoint),
        }

        _LOGGER.debug("Sending update to %s: %s", device_id, payload)
        try:
            status_code, _data, text = await self._request_with_auth(
                "PUT", f"{OLYMPIA_API_URL}/thermostats/{device_id}/settings/", data=payload
            )
        except Exception as err:
            _LOGGER.error("Error sending update for device %s: %s", device_id, err)
            raise HomeAssistantError(
                f"Error sending update for {device_id}: {err}"
            ) from err

        _LOGGER.debug("PUT response for %s: %d", device_id, status_code)
        if status_code != 200:
            _LOGGER.error(
                "Failed to send update for device %s: %d - %s",
                device_id, status_code, text,
            )
            raise HomeAssistantError(
                f"Device {device_id} rejected update: HTTP {status_code}"
            )

        if self.data and device_id in self.data:
            self.data[device_id]["status"].update({
                "is_on": turn_on,
                "boiler_on": boiler_on,
            })
            self.data[device_id].setdefault("setting", {})["setpoint"] = setpoint
            self.async_set_updated_data(self.data)

    async def _async_update_data(self) -> dict:
        """Fetch all thermostats (called on the coordinator interval)."""
        try:
            status, data, _text = await self._request_with_auth(
                "GET", f"{OLYMPIA_API_URL}/thermostats/"
            )
            if status != 200:
                raise UpdateFailed(f"Failed to fetch thermostats: {status}")
            thermostats = {
                device.get("id"): {
                    "device": device,
                    "status": device.get("status", {}),
                    "setting": device.get("setting", {}),
                }
                for device in (data or {}).get("results", [])
            }
            for dev_id, dev in thermostats.items():
                st = dev.get("status") or {}
                _LOGGER.debug(
                    "Poll %s: is_on=%s boiler_on=%s burner_on=%s "
                    "status.setpoint=%s setting.setpoint=%s",
                    dev_id,
                    st.get("is_on"),
                    st.get("boiler_on"),
                    st.get("burner_on"),
                    st.get("setpoint"),
                    (dev.get("setting") or {}).get("setpoint"),
                )
            _LOGGER.debug("Fetched %d Olympia thermostat(s)", len(thermostats))
            return thermostats
        except ConfigEntryAuthFailed:
            raise
        except InvalidAuth as err:
            raise ConfigEntryAuthFailed(str(err)) from err
        except UpdateFailed:
            raise
        except CannotConnect as err:
            raise UpdateFailed(str(err)) from err
        except Exception as err:
            raise UpdateFailed(f"Error fetching data: {err}") from err

    async def _request_with_auth(
        self, method: str, url: str, **kwargs: Any
    ) -> tuple[int, Optional[dict], str]:
        """Make an authenticated request, refreshing the token once on 401.

        Returns ``(status_code, parsed_json_or_None, raw_text)``.
        """
        session = self._session or async_get_clientsession(self.hass)
        await self._ensure_valid_token()

        for attempt in range(2):
            async with session.request(
                method,
                url,
                headers={"Authorization": f"JWT {self._auth_token}"},
                timeout=REQUEST_TIMEOUT,
                **kwargs,
            ) as resp:
                if resp.status == 401 and attempt == 0:
                    _LOGGER.warning("Got 401 on %s, refreshing token and retrying", url)
                    await self._refresh_token()
                    continue
                text = await resp.text()
                try:
                    data = await resp.json()
                except Exception:
                    data = None
                return resp.status, data, text

    async def _ensure_valid_token(self) -> None:
        """Refresh the token if missing or within 120s of expiry."""
        if self._auth_token and self._token_expires_at:
            if time.time() < self._token_expires_at - TOKEN_REFRESH_BUFFER:
                return
        await self._refresh_token()

    async def _refresh_token(self) -> None:
        """Log in and store a fresh JWT (plus its expiry)."""
        session = self._session or async_get_clientsession(self.hass)
        self._auth_token, self._token_expires_at = await async_login(
            session, self._email, self._password
        )
        _LOGGER.debug("Token refreshed successfully")


OlympiaConfigEntry = ConfigEntry[OlympiaElectronicsCoordinator]
