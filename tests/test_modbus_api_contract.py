"""Dependency-free behavior tests for the Modbus safety wrapper."""

from __future__ import annotations

import asyncio
import importlib.util
from pathlib import Path
import sys
from types import ModuleType
import unittest


ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = ROOT / "custom_components" / "siemens_sentron" / "modbus_api.py"


fake_package = ModuleType("pymodbus")
fake_client_module = ModuleType("pymodbus.client")
fake_client_module.AsyncModbusTcpClient = object
fake_package.client = fake_client_module
sys.modules.setdefault("pymodbus", fake_package)
sys.modules.setdefault("pymodbus.client", fake_client_module)

spec = importlib.util.spec_from_file_location("sentron_modbus_api", MODULE_PATH)
if spec is None or spec.loader is None:
    raise RuntimeError("Could not load modbus_api.py")
MODBUS_API = importlib.util.module_from_spec(spec)
spec.loader.exec_module(MODBUS_API)


class _Result:
    def __init__(self, *, error: bool = False, registers=None) -> None:
        self._error = error
        self.registers = registers

    def isError(self) -> bool:  # noqa: N802 - pymodbus API spelling
        return self._error


class _FakeClient:
    def __init__(self) -> None:
        self.active = 0
        self.max_active = 0
        self.read_calls = 0
        self.write_calls = 0
        self.write_single_calls = 0
        self.write_multiple_calls = 0
        self.write_result = _Result()
        self.holding_registers = None
        self.last_device_id = None
        self.last_write_address = None
        self.last_write_value = None
        self.last_write_values = None

    async def _yield_while_active(self) -> None:
        self.active += 1
        self.max_active = max(self.max_active, self.active)
        await asyncio.sleep(0)
        self.active -= 1

    async def read_input_registers(self, *, address, count, device_id):
        self.read_calls += 1
        self.last_device_id = device_id
        await self._yield_while_active()
        return _Result(registers=[address] * count)

    async def read_holding_registers(self, *, address, count, device_id):
        self.read_calls += 1
        self.last_device_id = device_id
        await self._yield_while_active()
        registers = (
            [address] * count
            if self.holding_registers is None
            else list(self.holding_registers)
        )
        return _Result(registers=registers)

    async def write_register(self, *, address, value, device_id):
        self.write_calls += 1
        self.write_single_calls += 1
        self.last_device_id = device_id
        self.last_write_address = address
        self.last_write_value = value
        await self._yield_while_active()
        return self.write_result

    async def write_registers(self, *, address, values, device_id):
        self.write_calls += 1
        self.write_multiple_calls += 1
        self.last_device_id = device_id
        self.last_write_address = address
        self.last_write_values = list(values)
        await self._yield_while_active()
        return self.write_result


class ModbusSafetyContractTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self) -> None:
        self.api = MODBUS_API.SentronModbusApi("127.0.0.1", 502)
        self.client = _FakeClient()
        self.api.client = self.client

    async def test_concurrent_requests_are_serialized(self) -> None:
        values = await asyncio.gather(
            self.api.read_input_u16(7, 100),
            self.api.read_input_u16(7, 101),
        )
        self.assertEqual(values, [100, 101])
        self.assertEqual(self.client.max_active, 1)
        self.assertEqual(self.client.read_calls, 2)
        self.assertEqual(self.client.last_device_id, 7)

    async def test_none_response_is_not_acknowledged_or_replayed(self) -> None:
        self.client.write_result = None
        self.assertFalse(await self.api.write_uint16(11, 3692, 1))
        self.assertEqual(self.client.write_calls, 1)

    async def test_error_response_is_not_acknowledged_or_replayed(self) -> None:
        self.client.write_result = _Result(error=True)
        self.assertFalse(await self.api.write_uint16(11, 3692, 1))
        self.assertEqual(self.client.write_calls, 1)

    async def test_explicit_success_is_acknowledged_once(self) -> None:
        self.client.write_result = _Result(error=False)
        self.assertTrue(await self.api.write_uint16(11, 3692, 1))
        self.assertEqual(self.client.write_calls, 1)

    async def test_read_holding_i16_decodes_signed_and_sentinel_values(self) -> None:
        self.client.holding_registers = [0xFFE4]
        self.assertEqual(await self.api.read_holding_i16(2, 1662), -28)
        self.client.holding_registers = [0xFFFF]
        self.assertIsNone(await self.api.read_holding_i16(2, 1662))
        self.assertEqual(self.client.read_calls, 2)
        self.assertEqual(self.client.last_device_id, 2)

    async def test_fc16_explicit_success_is_acknowledged_exactly_once(self) -> None:
        self.client.write_result = _Result(error=False)
        self.assertTrue(await self.api.write_registers(2, 1660, [0, 60]))
        self.assertEqual(self.client.write_multiple_calls, 1)
        self.assertEqual(self.client.write_calls, 1)
        self.assertEqual(self.client.last_write_address, 1660)
        self.assertEqual(self.client.last_write_values, [0, 60])
        self.assertEqual(self.client.last_device_id, 2)

    async def test_fc16_failure_is_not_replayed(self) -> None:
        for response in (None, _Result(error=True)):
            with self.subTest(response=response):
                self.client.write_result = response
                before = self.client.write_multiple_calls
                self.assertFalse(await self.api.write_registers(2, 1660, [0, 60]))
                self.assertEqual(self.client.write_multiple_calls, before + 1)

    async def test_fc16_shares_the_transaction_lock_with_reads(self) -> None:
        results = await asyncio.gather(
            self.api.write_registers(2, 1660, [0, 60]),
            self.api.read_holding_i16(2, 1662),
        )
        self.assertEqual(results, [True, 1662])
        self.assertEqual(self.client.max_active, 1)

    async def test_write_uint32_is_one_big_endian_fc16_transaction(self) -> None:
        self.assertTrue(await self.api.write_uint32(2, 1640, 0x12345678))
        self.assertEqual(self.client.write_multiple_calls, 1)
        self.assertEqual(self.client.write_single_calls, 0)
        self.assertEqual(self.client.last_write_address, 1640)
        self.assertEqual(self.client.last_write_values, [0x1234, 0x5678])

    async def test_write_register_value_validation_happens_before_io(self) -> None:
        invalid_blocks = ([], [-1], [0x10000], [0] * 124)
        for values in invalid_blocks:
            with self.subTest(values=values):
                with self.assertRaises(ValueError):
                    await self.api.write_registers(2, 1660, values)
        with self.assertRaises(ValueError):
            await self.api.write_uint32(2, 1640, 0x1_0000_0000)
        self.assertEqual(self.client.write_calls, 0)


if __name__ == "__main__":
    unittest.main()
