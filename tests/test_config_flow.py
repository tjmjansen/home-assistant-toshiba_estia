"""Tests for the Toshiba Estia config flow."""

from __future__ import annotations

import sys
import types


if "toshiba_estia.device_manager" not in sys.modules:
    toshiba_estia = types.ModuleType("toshiba_estia")
    toshiba_estia.__path__ = []
    device_manager = types.ModuleType("toshiba_estia.device_manager")

    class ToshibaAcDeviceManager:
        """Stub external package used while importing the config flow."""

    device_manager.ToshibaAcDeviceManager = ToshibaAcDeviceManager
    sys.modules["toshiba_estia"] = toshiba_estia
    sys.modules["toshiba_estia.device_manager"] = device_manager


from custom_components.toshiba_estia.config_flow import ConfigFlow, ToshibaOptionsFlow


def test_options_flow_does_not_set_config_entry_in_constructor() -> None:
    """Test options flow uses Home Assistant's config_entry property."""
    flow = ConfigFlow.async_get_options_flow(object())

    assert isinstance(flow, ToshibaOptionsFlow)
    assert "_config_entry" not in flow.__dict__
