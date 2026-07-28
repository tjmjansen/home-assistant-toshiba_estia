"""The Toshiba AC integration."""

from __future__ import annotations

import asyncio
import logging
import secrets

import aiohttp
from toshiba_estia.device_manager import ToshibaAcDeviceManager
from toshiba_estia.utils import http_api as toshiba_http_api
from toshiba_estia.utils.http_api import ToshibaAcHttpApiAuthError, ToshibaAcHttpApiError

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed, ConfigEntryNotReady

from .const import DOMAIN

PLATFORMS = ["climate", "sensor", "water_heater", "binary_sensor", "switch"]
CONNECT_TIMEOUT = 30

_LOGGER = logging.getLogger(__name__)

_original_request_api = toshiba_http_api.ToshibaAcHttpApi.request_api


async def _patched_request_api(
    self: toshiba_http_api.ToshibaAcHttpApi, *args, **kwargs
):
    """Create Toshiba API sessions with the Device-ID header required by the WAF."""
    if not self.session or self.session.closed:
        timeout = aiohttp.ClientTimeout(total=20, connect=10, sock_read=15)
        self.session = aiohttp.ClientSession(
            timeout=timeout,
            headers={"Device-ID": secrets.token_hex(8)},
        )

    return await _original_request_api(self, *args, **kwargs)


toshiba_http_api.ToshibaAcHttpApi.request_api = _patched_request_api


async def sas_token_updated_for_entry(
    hass: HomeAssistant, entry: ConfigEntry, new_sas_token: str
):
    """Update SAS token."""
    _LOGGER.info("SAS token updated")

    new_data = {**entry.data, "sas_token": new_sas_token}
    hass.config_entries.async_update_entry(entry, data=new_data)


def add_sas_token_updated_callback_for_entry(
    hass: HomeAssistant, entry: ConfigEntry, device_manager: ToshibaAcDeviceManager
):
    """Set up SAS token update callback."""

    async def wrapper_callback(new_sas_token: str):
        await sas_token_updated_for_entry(hass, entry, new_sas_token)

    device_manager.on_sas_token_updated_callback.add(wrapper_callback)


async def connect_device_manager(device_manager: ToshibaAcDeviceManager) -> str | None:
    """Connect to Toshiba, bounded by Home Assistant setup expectations."""
    return await asyncio.wait_for(device_manager.connect(), timeout=CONNECT_TIMEOUT)


async def async_setup(hass: HomeAssistant, config: dict):
    """Set up the Hello World component."""
    # Ensure our name space for storing objects is a known type. A dict is
    # common/preferred as it allows a separate instance of your class for each
    # instance that has been created in the UI.
    hass.data.setdefault(DOMAIN, {})

    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Toshiba AC from a config entry."""
    device_manager = ToshibaAcDeviceManager(
        entry.data["username"],
        entry.data["password"],
        entry.data["device_id"],
        entry.data["sas_token"],
    )

    try:
        await connect_device_manager(device_manager)
    except ToshibaAcHttpApiAuthError as ex:
        _LOGGER.warning("Initial connection failed, trying to get new sas_token...")
        # If it fails to connect, try to get a new sas_token
        device_manager = ToshibaAcDeviceManager(
            entry.data["username"], entry.data["password"], entry.data["device_id"]
        )

        try:
            new_sas_token = await connect_device_manager(device_manager)

            _LOGGER.info("Successfully got new sas_token!")

            # Save new sas_token
            new_data = {**entry.data, "sas_token": new_sas_token}
            hass.config_entries.async_update_entry(entry, data=new_data)
        except ToshibaAcHttpApiAuthError as auth_ex:
            _LOGGER.warning("Authentication failed while refreshing sas_token")
            raise ConfigEntryAuthFailed from auth_ex
        except (ToshibaAcHttpApiError, TimeoutError) as refresh_ex:
            _LOGGER.warning("Connection failed while refreshing sas_token")
            raise ConfigEntryNotReady from refresh_ex
        except Exception as refresh_ex:
            _LOGGER.warning("Unexpected error while refreshing sas_token")
            raise ConfigEntryNotReady from refresh_ex
    except (ToshibaAcHttpApiError, TimeoutError) as ex:
        _LOGGER.warning("Connection to Toshiba server failed")
        raise ConfigEntryNotReady from ex
    except Exception as ex:
        _LOGGER.warning("Unexpected error while connecting to Toshiba server")
        raise ConfigEntryNotReady from ex

    add_sas_token_updated_callback_for_entry(hass, entry, device_manager)

    hass.data[DOMAIN][entry.entry_id] = device_manager

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    _LOGGER.error("Unload Toshiba integration")
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        device_manager: ToshibaAcDeviceManager = hass.data[DOMAIN][entry.entry_id]
        try:
            await device_manager.shutdown()
        except Exception as ex:
            _LOGGER.error("Error while unloading Toshiba integration %s", ex)
        hass.data[DOMAIN].pop(entry.entry_id)

    return unload_ok
