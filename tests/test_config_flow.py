"""Tests for the Toshiba Estia config flow."""

from __future__ import annotations

import sys
import types

import pytest


if "toshiba_estia.device_manager" not in sys.modules:
    toshiba_estia = types.ModuleType("toshiba_estia")
    toshiba_estia.__path__ = []
    device_manager = types.ModuleType("toshiba_estia.device_manager")
    http_api = types.ModuleType("toshiba_estia.utils.http_api")
    utils = types.ModuleType("toshiba_estia.utils")

    class ToshibaAcDeviceManager:
        """Stub external package used while importing the config flow."""

    class ToshibaAcHttpApiAuthError(Exception):
        """Stub auth error from external package."""

    class ToshibaAcHttpApiError(Exception):
        """Stub API error from external package."""

    device_manager.ToshibaAcDeviceManager = ToshibaAcDeviceManager
    http_api.ToshibaAcHttpApiAuthError = ToshibaAcHttpApiAuthError
    http_api.ToshibaAcHttpApiError = ToshibaAcHttpApiError
    sys.modules["toshiba_estia"] = toshiba_estia
    sys.modules["toshiba_estia.device_manager"] = device_manager
    sys.modules["toshiba_estia.utils"] = utils
    sys.modules["toshiba_estia.utils.http_api"] = http_api


from homeassistant.exceptions import ConfigEntryNotReady
from toshiba_estia.utils.http_api import ToshibaAcHttpApiError

from custom_components.toshiba_estia import async_setup_entry
from custom_components.toshiba_estia.config_flow import ConfigFlow, ToshibaOptionsFlow


def test_options_flow_does_not_set_config_entry_in_constructor() -> None:
    """Test options flow uses Home Assistant's config_entry property."""
    flow = ConfigFlow.async_get_options_flow(object())

    assert isinstance(flow, ToshibaOptionsFlow)
    assert "_config_entry" not in flow.__dict__


@pytest.mark.asyncio
async def test_setup_entry_does_not_retry_on_transient_api_error(monkeypatch) -> None:
    """Test setup lets Home Assistant retry instead of logging in again."""
    connect_calls = []

    class DeviceManager:
        def __init__(self, *args):
            self.on_sas_token_updated_callback = set()

        async def connect(self):
            connect_calls.append(1)
            raise ToshibaAcHttpApiError("Too many requests. Try again in 60 seconds.")

    class Entry:
        entry_id = "entry-id"
        data = {
            "username": "user",
            "password": "password",
            "device_id": "device-id",
            "sas_token": "sas-token",
        }

    monkeypatch.setattr(
        "custom_components.toshiba_estia.ToshibaAcDeviceManager", DeviceManager
    )

    with pytest.raises(ConfigEntryNotReady):
        await async_setup_entry(object(), Entry())

    assert len(connect_calls) == 1
