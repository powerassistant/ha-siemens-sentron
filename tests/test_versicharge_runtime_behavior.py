"""Dependency-free behavioral tests for VersiCharge runtime controls.

These tests load the real coordinator and Number platform in an isolated
package namespace.  Small Home Assistant and Modbus stubs keep the tests
executable in the repository's dependency-free validation environment.
"""

from __future__ import annotations

import asyncio
import importlib.util
from pathlib import Path
import sys
from types import ModuleType
import unittest


ROOT = Path(__file__).resolve().parents[1]
INTEGRATION = ROOT / "custom_components" / "siemens_sentron"
TEST_PACKAGE = "_sentron_versicharge_runtime_test"
_MISSING = object()


def _module(name: str, **attributes: object) -> ModuleType:
    module = ModuleType(name)
    for key, value in attributes.items():
        setattr(module, key, value)
    return module


def _load_module(name: str, path: Path) -> ModuleType:
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Could not load {path.name}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


class _HomeAssistantError(Exception):
    """Minimal replacement for Home Assistant service errors."""


class _ConfigEntryNotReady(Exception):
    """Minimal replacement for config-entry setup errors."""


class _UpdateFailed(Exception):
    """Minimal replacement for coordinator update errors."""


class _DataUpdateCoordinator:
    @classmethod
    def __class_getitem__(cls, item):
        return cls

    def __init__(self, hass, logger, *, name, update_interval) -> None:
        self.hass = hass
        self.data = None
        self.last_update_success = True
        self.update_interval = update_interval
        self.listener_updates = 0

    def async_update_listeners(self) -> None:
        self.listener_updates += 1

    async def async_shutdown(self) -> None:
        return None


class _CoordinatorEntity:
    @classmethod
    def __class_getitem__(cls, item):
        return cls

    def __init__(self, coordinator) -> None:
        self.coordinator = coordinator
        self.state_writes = 0

    @property
    def available(self) -> bool:
        return self.coordinator.last_update_success

    async def async_added_to_hass(self) -> None:
        return None

    def async_write_ha_state(self) -> None:
        self.state_writes += 1


class _NumberEntity:
    @property
    def native_step(self):
        return self._attr_native_step


class _DeviceInfo(dict):
    def __init__(self, **values) -> None:
        super().__init__(**values)


class _SentronModbusApiStub:
    def __init__(self, *args, **kwargs) -> None:
        self.successful_read_count = 0


def _load_runtime_modules() -> tuple[ModuleType, ModuleType]:
    replacements: dict[str, object] = {}

    def replace(name: str, module: ModuleType) -> None:
        replacements[name] = sys.modules.get(name, _MISSING)
        sys.modules[name] = module

    package = _module(TEST_PACKAGE)
    package.__path__ = [str(INTEGRATION)]
    sys.modules[TEST_PACKAGE] = package

    homeassistant = _module("homeassistant")
    homeassistant.__path__ = []
    components = _module("homeassistant.components")
    components.__path__ = []
    helpers = _module("homeassistant.helpers")
    helpers.__path__ = []

    entity_category = type(
        "EntityCategory", (), {"CONFIG": "config", "DIAGNOSTIC": "diagnostic"}
    )
    number_device_class = type(
        "NumberDeviceClass",
        (),
        {"CURRENT": "current", "DURATION": "duration", "POWER": "power"},
    )
    number_mode = type("NumberMode", (), {"BOX": "box"})
    electric_current = type(
        "UnitOfElectricCurrent", (), {"AMPERE": "A", "MILLIAMPERE": "mA"}
    )
    power = type("UnitOfPower", (), {"WATT": "W", "KILO_WATT": "kW"})
    duration = type("UnitOfTime", (), {"SECONDS": "s"})

    external_stubs = {
        "homeassistant": homeassistant,
        "homeassistant.components": components,
        "homeassistant.components.number": _module(
            "homeassistant.components.number",
            NumberDeviceClass=number_device_class,
            NumberEntity=_NumberEntity,
            NumberMode=number_mode,
        ),
        "homeassistant.config_entries": _module(
            "homeassistant.config_entries", ConfigEntry=object
        ),
        "homeassistant.const": _module(
            "homeassistant.const",
            CONF_HOST="host",
            CONF_PORT="port",
            EntityCategory=entity_category,
            PERCENTAGE="%",
            UnitOfElectricCurrent=electric_current,
            UnitOfPower=power,
            UnitOfTime=duration,
        ),
        "homeassistant.core": _module(
            "homeassistant.core", HomeAssistant=object, callback=lambda method: method
        ),
        "homeassistant.exceptions": _module(
            "homeassistant.exceptions",
            ConfigEntryNotReady=_ConfigEntryNotReady,
            HomeAssistantError=_HomeAssistantError,
        ),
        "homeassistant.helpers": helpers,
        "homeassistant.helpers.device_registry": _module(
            "homeassistant.helpers.device_registry", DeviceInfo=_DeviceInfo
        ),
        "homeassistant.helpers.entity_platform": _module(
            "homeassistant.helpers.entity_platform", AddEntitiesCallback=object
        ),
        "homeassistant.helpers.update_coordinator": _module(
            "homeassistant.helpers.update_coordinator",
            CoordinatorEntity=_CoordinatorEntity,
            DataUpdateCoordinator=_DataUpdateCoordinator,
            UpdateFailed=_UpdateFailed,
        ),
    }
    for name, module in external_stubs.items():
        replace(name, module)

    try:
        _load_module(f"{TEST_PACKAGE}.const", INTEGRATION / "const.py")
        _load_module(f"{TEST_PACKAGE}.device_types", INTEGRATION / "device_types.py")
        _load_module(f"{TEST_PACKAGE}.entity_ids", INTEGRATION / "entity_ids.py")
        _load_module(f"{TEST_PACKAGE}.versicharge", INTEGRATION / "versicharge.py")

        async def empty_async_result(*args, **kwargs):
            return []

        sys.modules[f"{TEST_PACKAGE}.discovery"] = _module(
            f"{TEST_PACKAGE}.discovery", async_discover_slaves=empty_async_result
        )
        sys.modules[f"{TEST_PACKAGE}.gateway"] = _module(
            f"{TEST_PACKAGE}.gateway", async_build_gateway_data=empty_async_result
        )
        sys.modules[f"{TEST_PACKAGE}.profiles"] = _module(
            f"{TEST_PACKAGE}.profiles", get_effective_device_profile=lambda device: []
        )
        sys.modules[f"{TEST_PACKAGE}.pac2200"] = _module(
            f"{TEST_PACKAGE}.pac2200", PAC2200_SENSORS=(), PAC2200_SLAVE_ID=1
        )
        sys.modules[f"{TEST_PACKAGE}.modbus_api"] = _module(
            f"{TEST_PACKAGE}.modbus_api", SentronModbusApi=_SentronModbusApiStub
        )

        coordinator = _load_module(
            f"{TEST_PACKAGE}.coordinator", INTEGRATION / "coordinator.py"
        )
        number = _load_module(f"{TEST_PACKAGE}.number", INTEGRATION / "number.py")
        return coordinator, number
    finally:
        for name, previous in replacements.items():
            if previous is _MISSING:
                sys.modules.pop(name, None)
            else:
                sys.modules[name] = previous


COORDINATOR, NUMBER = _load_runtime_modules()


class _Entry:
    entry_id = "runtime_test"
    title = "VersiCharge Test"
    data = {"host": "127.0.0.1", "port": 502, "device_kind": "versicharge"}


class _NumberCoordinator:
    last_update_success = True
    versicharge_current_control_available = True
    versicharge_target_current = 6
    versicharge_target_power_kw = 4.1
    versicharge_installation_current = 16
    versicharge_profile = "modern"

    def __init__(self) -> None:
        self.data = {
            "gateway": {
                "device_kind": "versicharge",
                "unit_id": 2,
                "id": "versicharge-test",
                "name": "VersiCharge Test",
                "model": "8EM",
            },
            "values": {
                2: {
                    "effective_phase_count": 3,
                    "charging_current_limit_fresh": False,
                    "active_power_total": 0,
                    "voltage_l1_n": 230,
                }
            },
        }

    def get_versicharge_values(self) -> dict:
        return self.data["values"][2]


class _CommandModbus:
    def __init__(self, *, block: asyncio.Event | None = None) -> None:
        self.block = block
        self.writes: list[tuple[int, int, int]] = []
        self.reads = 0
        self.successful_read_count = 0

    async def write_uint16(self, unit_id: int, address: int, value: int) -> bool:
        self.writes.append((unit_id, address, value))
        if self.block is not None:
            await self.block.wait()
        return True

    async def read_holding_u16(self, unit_id: int, address: int) -> int:
        self.reads += 1
        raise AssertionError("control path must not perform an immediate readback")


class VersiChargeRuntimeBehaviorTests(unittest.TestCase):
    def test_target_numbers_survive_missing_readback_and_telemetry_polls(self) -> None:
        coordinator = _NumberCoordinator()
        power = NUMBER.VersiChargeChargingPowerNumber(coordinator, _Entry())

        self.assertTrue(power.available)
        self.assertEqual(power.native_value, 4.1)
        self.assertEqual(power.native_min_value, 4.1)
        self.assertEqual(power.native_max_value, 11.0)
        self.assertEqual(power.native_step, 0.1)

        asyncio.run(power.async_added_to_hass())
        values = coordinator.get_versicharge_values()
        values["active_power_total"] = 7_000
        values["voltage_l1_n"] = 236
        values["current_l1"] = 10
        values["current_l2"] = 0
        values["current_l3"] = 0
        power._handle_coordinator_update()

        self.assertEqual(power.state_writes, 0)
        self.assertEqual(power.native_value, 4.1)

        coordinator.versicharge_target_power_kw = 5.0
        power._handle_coordinator_update()
        self.assertEqual(power.state_writes, 1)
        self.assertEqual(power.native_value, 5.0)

    def _coordinator(self, *, current_limit: float | None = 7.0):
        coordinator = COORDINATOR.SentronCoordinator(object(), _Entry())
        coordinator.data = {
            "gateway": {
                "device_kind": "versicharge",
                "unit_id": 2,
                "register_profile": "modern",
                "installation_current": 16,
            },
            "slaves": [],
            "values": {
                2: {
                    "effective_phase_count": 3,
                    "voltage_l1_n": 230,
                    "voltage_l2_n": 230,
                    "voltage_l3_n": 230,
                    "power_factor_l1": 1,
                    "power_factor_l2": 1,
                    "power_factor_l3": 1,
                    "charging_current_limit": current_limit,
                    "charging_current_limit_raw": (
                        int(current_limit) if current_limit is not None else None
                    ),
                    "charging_current_limit_fresh": current_limit is not None,
                    "evse_state": "charging",
                    "current_l1": 7,
                    "current_l2": 7,
                    "current_l3": 7,
                    "active_power_total": 4_800,
                }
            },
        }
        coordinator.last_update_success = True
        coordinator._versicharge_target_power_kw = 4.8
        return coordinator

    def test_active_charge_writes_one_whole_amp_without_readback(self) -> None:
        coordinator = self._coordinator(current_limit=7.0)
        coordinator.modbus = _CommandModbus()

        asyncio.run(coordinator.async_set_versicharge_target_power_kw(6.9))

        self.assertEqual(coordinator.versicharge_target_current, 10)
        self.assertEqual(coordinator.versicharge_target_power_kw, 6.9)
        self.assertEqual(coordinator.modbus.writes, [(2, 1633, 10)])
        self.assertEqual(coordinator.modbus.reads, 0)
        values = coordinator.get_versicharge_values()
        self.assertEqual(values["charging_current_limit_raw"], 10)
        self.assertEqual(values["charging_current_limit"], 10.0)
        self.assertTrue(values["charging_current_limit_fresh"])
        self.assertEqual(values["charging_current_limit_source"], "write_ack")

        # Identical kW and noisy measurements cannot create another command.
        values["voltage_l1_n"] = 241
        values["voltage_l2_n"] = 218
        values["voltage_l3_n"] = 235
        values["power_factor_l1"] = 0.81
        values["power_factor_l2"] = 0.97
        values["power_factor_l3"] = 0.88
        asyncio.run(coordinator.async_set_versicharge_target_power_kw(6.9))
        self.assertEqual(coordinator.modbus.writes, [(2, 1633, 10)])

    def test_identical_target_is_a_complete_no_op(self) -> None:
        coordinator = self._coordinator(current_limit=10.0)
        coordinator.modbus = _CommandModbus()
        coordinator._versicharge_target_power_kw = 6.9

        asyncio.run(coordinator.async_set_versicharge_target_power_kw(6.9))

        self.assertEqual(coordinator.modbus.writes, [])
        self.assertEqual(coordinator.listener_updates, 0)

    def test_paused_target_is_stored_without_modbus_io(self) -> None:
        coordinator = self._coordinator(current_limit=0.0)
        coordinator.modbus = _CommandModbus()

        asyncio.run(coordinator.async_set_versicharge_target_power_kw(6.9))

        self.assertEqual(coordinator.versicharge_target_power_kw, 6.9)
        self.assertEqual(coordinator.modbus.writes, [])

    def test_paused_target_changes_are_rate_limited_without_listener_flood(self) -> None:
        coordinator = self._coordinator(current_limit=0.0)
        coordinator.modbus = _CommandModbus()

        asyncio.run(coordinator.async_set_versicharge_target_power_kw(6.9))
        with self.assertRaisesRegex(_HomeAssistantError, "rate limit"):
            asyncio.run(coordinator.async_set_versicharge_target_power_kw(7.6))

        self.assertEqual(coordinator.versicharge_target_power_kw, 6.9)
        self.assertEqual(coordinator.modbus.writes, [])
        self.assertEqual(coordinator.listener_updates, 1)

    def test_paused_target_can_be_resumed_immediately(self) -> None:
        coordinator = self._coordinator(current_limit=0.0)
        coordinator.modbus = _CommandModbus()

        async def run() -> None:
            await coordinator.async_set_versicharge_target_power_kw(6.9)
            await coordinator.async_set_versicharge_enabled(True)

        asyncio.run(run())

        self.assertEqual(coordinator.versicharge_target_power_kw, 6.9)
        self.assertEqual(coordinator.modbus.writes, [(2, 1633, 10)])
        self.assertEqual(coordinator.listener_updates, 2)

    def test_unknown_current_limit_rejects_target_without_writing(self) -> None:
        coordinator = self._coordinator(current_limit=None)
        coordinator.modbus = _CommandModbus()

        with self.assertRaisesRegex(_HomeAssistantError, "readback is unavailable"):
            asyncio.run(coordinator.async_set_versicharge_target_power_kw(6.9))

        self.assertEqual(coordinator.versicharge_target_power_kw, 4.8)
        self.assertEqual(coordinator.modbus.writes, [])

    def test_concurrent_target_calls_are_rejected_not_queued(self) -> None:
        async def run() -> tuple[int, list[object]]:
            gate = asyncio.Event()
            coordinator = self._coordinator(current_limit=7.0)
            coordinator.modbus = _CommandModbus(block=gate)
            first = asyncio.create_task(
                coordinator.async_set_versicharge_target_power_kw(6.9)
            )
            await asyncio.sleep(0)
            followers = await asyncio.gather(
                *(
                    coordinator.async_set_versicharge_target_power_kw(7.6)
                    for _ in range(1_000)
                ),
                return_exceptions=True,
            )
            self.assertFalse(first.done())
            gate.set()
            await first
            return len(coordinator.modbus.writes), followers

        writes, followers = asyncio.run(run())
        self.assertEqual(writes, 1)
        self.assertTrue(
            all(
                isinstance(result, _HomeAssistantError)
                and "no command was queued" in str(result)
                for result in followers
            )
        )

    def test_cancelled_command_releases_fail_fast_guard(self) -> None:
        async def run() -> bool:
            gate = asyncio.Event()
            coordinator = self._coordinator(current_limit=7.0)
            coordinator.modbus = _CommandModbus(block=gate)
            command = asyncio.create_task(
                coordinator.async_set_versicharge_target_power_kw(6.9)
            )
            await asyncio.sleep(0)
            self.assertTrue(coordinator._versicharge_command_in_progress)
            command.cancel()
            with self.assertRaises(asyncio.CancelledError):
                await command
            return coordinator._versicharge_command_in_progress

        self.assertFalse(asyncio.run(run()))

    def test_target_is_rejected_while_resume_is_in_progress(self) -> None:
        async def run() -> tuple[object, list[tuple[int, int, int]], int]:
            gate = asyncio.Event()
            coordinator = self._coordinator(current_limit=0.0)
            coordinator.modbus = _CommandModbus(block=gate)
            coordinator._versicharge_target_power_kw = 4.1
            resume = asyncio.create_task(coordinator.async_set_versicharge_enabled(True))
            await asyncio.sleep(0)
            with self.assertRaisesRegex(_HomeAssistantError, "no command was queued"):
                await coordinator.async_set_versicharge_target_power_kw(6.9)
            gate.set()
            await resume
            return (
                coordinator.versicharge_target_power_kw,
                coordinator.modbus.writes,
                coordinator.listener_updates,
            )

        target, writes, updates = asyncio.run(run())
        self.assertEqual(target, 4.1)
        self.assertEqual(writes, [(2, 1633, 6)])
        self.assertEqual(updates, 1)

    def test_switch_no_op_is_rejected_while_opposite_command_is_in_progress(self) -> None:
        async def run() -> tuple[list[tuple[int, int, int]], bool]:
            gate = asyncio.Event()
            coordinator = self._coordinator(current_limit=7.0)
            coordinator.modbus = _CommandModbus(block=gate)
            pause = asyncio.create_task(coordinator.async_set_versicharge_enabled(False))
            await asyncio.sleep(0)
            with self.assertRaisesRegex(_HomeAssistantError, "no command was queued"):
                await coordinator.async_set_versicharge_enabled(True)
            gate.set()
            await pause
            return (
                coordinator.modbus.writes,
                coordinator._versicharge_command_in_progress,
            )

        writes, in_progress = asyncio.run(run())
        self.assertEqual(writes, [(2, 1633, 0)])
        self.assertFalse(in_progress)

    def test_timed_out_command_is_not_retried_and_releases_guard(self) -> None:
        async def run() -> tuple[object, int, bool, float, int]:
            coordinator = self._coordinator(current_limit=7.0)
            coordinator.modbus = _CommandModbus(block=asyncio.Event())
            old_timeout = COORDINATOR.VERSICHARGE_COMMAND_TIMEOUT_SECONDS
            COORDINATOR.VERSICHARGE_COMMAND_TIMEOUT_SECONDS = 0.01
            try:
                with self.assertRaisesRegex(_HomeAssistantError, "not retried"):
                    await coordinator.async_set_versicharge_target_power_kw(6.9)
            finally:
                COORDINATOR.VERSICHARGE_COMMAND_TIMEOUT_SECONDS = old_timeout
            return (
                coordinator.versicharge_target_power_kw,
                len(coordinator.modbus.writes),
                coordinator._versicharge_command_in_progress,
                coordinator.get_versicharge_values()["charging_current_limit"],
                coordinator.listener_updates,
            )

        target, writes, in_progress, current_limit, updates = asyncio.run(run())
        self.assertEqual(target, 4.8)
        self.assertEqual(writes, 1)
        self.assertFalse(in_progress)
        self.assertEqual(current_limit, 7.0)
        self.assertEqual(updates, 0)

    def test_different_commands_are_rate_limited_without_waiting(self) -> None:
        coordinator = self._coordinator(current_limit=7.0)
        coordinator.modbus = _CommandModbus()
        asyncio.run(coordinator.async_set_versicharge_target_power_kw(6.9))

        with self.assertRaisesRegex(_HomeAssistantError, "rate limit"):
            asyncio.run(coordinator.async_set_versicharge_target_power_kw(7.6))

        self.assertEqual(coordinator.modbus.writes, [(2, 1633, 10)])


if __name__ == "__main__":
    unittest.main()
