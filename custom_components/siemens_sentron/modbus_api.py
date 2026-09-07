"""Modbus API helper for Siemens SENTRON."""

from __future__ import annotations

import asyncio
import logging
import struct

from pymodbus.client import AsyncModbusTcpClient

_LOGGER = logging.getLogger(__name__)


class SentronModbusApi:
    """Wrapper around pymodbus async client."""

    def __init__(self, host: str, port: int, timeout: int = 15) -> None:
        self.host = host
        self.port = port
        self.timeout = timeout
        self.client: AsyncModbusTcpClient | None = None
        # pymodbus' asynchronous client still represents one Modbus/TCP
        # transaction stream.  Coordinator refreshes and entity service calls
        # may run concurrently, so every request must share one lock.
        self._io_lock = asyncio.Lock()
        self._successful_read_count = 0

    @property
    def successful_read_count(self) -> int:
        """Return the number of reads that received a valid Modbus response."""
        return self._successful_read_count

    async def async_connect(self) -> bool:
        _LOGGER.debug(
            "Verbinde zu Siemens SENTRON Gateway %s:%s (timeout=%s)",
            self.host,
            self.port,
            self.timeout,
        )
        async with self._io_lock:
            self.client = AsyncModbusTcpClient(
                host=self.host,
                port=self.port,
                timeout=self.timeout,
                retries=0,
            )
            connected = await self.client.connect()
        _LOGGER.debug("TCP connect result for %s:%s: %s", self.host, self.port, connected)
        return bool(connected)

    async def async_close(self) -> None:
        async with self._io_lock:
            if self.client:
                self.client.close()
                self.client = None

    async def _read_registers(
        self,
        *,
        kind: str,
        slave: int,
        address: int,
        count: int,
    ) -> list[int] | None:
        async with self._io_lock:
            client = self.client
            if client is None:
                return None

            try:
                if kind == "input":
                    result = await client.read_input_registers(
                        address=address,
                        count=count,
                        device_id=slave,
                    )
                else:
                    result = await client.read_holding_registers(
                        address=address,
                        count=count,
                        device_id=slave,
                    )

                is_error = getattr(result, "isError", None)
                registers = getattr(result, "registers", None)
                if callable(is_error) and not is_error() and registers:
                    self._successful_read_count += 1
                    return [int(value) for value in registers]
            except Exception as err:  # noqa: BLE001
                _LOGGER.debug(
                    "%s read exception slave=%s address=%s count=%s err=%r",
                    kind,
                    slave,
                    address,
                    count,
                    err,
                )

        return None

    async def read_input_u16(self, slave: int, address: int) -> int | None:
        regs = await self._read_registers(kind="input", slave=slave, address=address, count=1)
        return None if not regs else int(regs[0])

    async def read_input_i16(self, slave: int, address: int) -> int | None:
        value = await self.read_input_u16(slave, address)
        if value is None:
            return None
        return value - 0x10000 if value & 0x8000 else value

    async def read_holding_registers(self, slave: int, address: int, count: int) -> list[int] | None:
        return await self._read_registers(kind="holding", slave=slave, address=address, count=count)

    async def read_holding_u16(self, slave: int, address: int) -> int | None:
        regs = await self._read_registers(kind="holding", slave=slave, address=address, count=1)
        return None if not regs else int(regs[0])

    async def read_holding_i16(self, slave: int, address: int) -> int | None:
        """Read a signed 16-bit holding register."""
        value = await self.read_holding_u16(slave, address)
        if value is None or value == 0xFFFF:
            return None
        return value - 0x10000 if value & 0x8000 else value

    async def read_holding_u32(self, slave: int, address: int) -> int | None:
        regs = await self._read_registers(kind="holding", slave=slave, address=address, count=2)
        if not regs or len(regs) != 2:
            return None
        return (int(regs[0]) << 16) | int(regs[1])

    async def read_input_u32(self, slave: int, address: int) -> int | None:
        regs = await self._read_registers(kind="input", slave=slave, address=address, count=2)
        if not regs or len(regs) != 2:
            return None
        return (int(regs[0]) << 16) | int(regs[1])

    async def read_input_float32(self, slave: int, address: int) -> float | None:
        regs = await self._read_registers(kind="input", slave=slave, address=address, count=2)
        if not regs or len(regs) != 2:
            return None
        try:
            return struct.unpack(">f", struct.pack(">HH", regs[0], regs[1]))[0]
        except Exception:
            return None

    async def read_input_float64(self, slave: int, address: int) -> float | None:
        regs = await self._read_registers(kind="input", slave=slave, address=address, count=4)
        return self._decode_float64(regs)

    async def read_holding_float32(self, slave: int, address: int) -> float | None:
        regs = await self._read_registers(kind="holding", slave=slave, address=address, count=2)
        if not regs or len(regs) != 2:
            return None
        try:
            return struct.unpack(">f", struct.pack(">HH", regs[0], regs[1]))[0]
        except Exception:
            return None

    async def read_holding_float64(self, slave: int, address: int) -> float | None:
        regs = await self._read_registers(kind="holding", slave=slave, address=address, count=4)
        return self._decode_float64(regs)

    def _decode_float64(self, regs: list[int] | None) -> float | None:
        if not regs or len(regs) != 4:
            return None
        try:
            return struct.unpack(">d", struct.pack(">HHHH", regs[0], regs[1], regs[2], regs[3]))[0]
        except Exception:
            return None

    async def read_input_string(self, slave: int, address: int, count: int = 2) -> str | None:
        regs = await self._read_registers(kind="input", slave=slave, address=address, count=count)
        return self._decode_ascii(regs)

    async def read_holding_string(self, slave: int, address: int, count: int = 2) -> str | None:
        regs = await self._read_registers(kind="holding", slave=slave, address=address, count=count)
        return self._decode_ascii(regs)

    async def read_holding_firmware_version(
        self,
        slave: int,
        address: int,
        count: int = 2,
    ) -> str | None:
        regs = await self._read_registers(kind="holding", slave=slave, address=address, count=count)
        if not regs:
            return None

        raw_bytes: list[int] = []
        for reg in regs:
            raw_bytes.append((reg >> 8) & 0xFF)
            raw_bytes.append(reg & 0xFF)

        if len(raw_bytes) < 4:
            return None

        prefix = raw_bytes[0]
        major = raw_bytes[1]
        minor = raw_bytes[2]
        patch = raw_bytes[3]

        prefix_char = chr(prefix) if 32 <= prefix <= 126 else "V"
        return f"{prefix_char}{major}.{minor}.{patch}"

    async def write_uint16(self, slave: int, address: int, value: int) -> bool:
        """Write one uint16 register exactly once.

        A timeout does not prove that the device rejected a request.  Retrying a
        command can therefore execute it repeatedly; callers receive ``False``
        unless pymodbus returns an explicit successful acknowledgement.
        """
        async with self._io_lock:
            client = self.client
            if client is None:
                return False

            try:
                result = await client.write_register(
                    address=address,
                    value=value,
                    device_id=slave,
                )
            except Exception as err:  # noqa: BLE001
                _LOGGER.debug(
                    "write_register exception slave=%s address=%s value=%s err=%r",
                    slave,
                    address,
                    value,
                    err,
                )
                return False

            ok = self._write_result_ok(result)
            _LOGGER.debug(
                "write_register result slave=%s address=%s value=%s ok=%s result=%r",
                slave,
                address,
                value,
                ok,
                result,
            )
            return ok

    async def write_registers(
        self, slave: int, address: int, values: list[int]
    ) -> bool:
        """Write one documented register block exactly once using FC16."""
        if not values or len(values) > 123:
            raise ValueError("A Modbus write requires 1..123 registers")
        normalized = [int(value) for value in values]
        if any(value < 0 or value > 0xFFFF for value in normalized):
            raise ValueError("Modbus register values must be uint16")

        async with self._io_lock:
            client = self.client
            if client is None:
                return False
            try:
                result = await client.write_registers(
                    address=address,
                    values=normalized,
                    device_id=slave,
                )
            except Exception as err:  # noqa: BLE001
                _LOGGER.debug(
                    "write_registers exception slave=%s address=%s values=%s err=%r",
                    slave,
                    address,
                    normalized,
                    err,
                )
                return False

            ok = self._write_result_ok(result)
            _LOGGER.debug(
                "write_registers result slave=%s address=%s values=%s ok=%s result=%r",
                slave,
                address,
                normalized,
                ok,
                result,
            )
            return ok

    async def write_uint32(self, slave: int, address: int, value: int) -> bool:
        """Write one high-word-first unsigned 32-bit value using FC16."""
        normalized = int(value)
        if not 0 <= normalized <= 0xFFFFFFFF:
            raise ValueError("uint32 value is outside 0..4294967295")
        return await self.write_registers(
            slave,
            address,
            [(normalized >> 16) & 0xFFFF, normalized & 0xFFFF],
        )

    @staticmethod
    def _write_result_ok(result) -> bool:
        """Return True only for an explicit successful pymodbus response."""
        if result is None:
            return False
        is_error = getattr(result, "isError", None)
        return callable(is_error) and not bool(is_error())

    async def read_input_output_forcing(self, slave: int, address: int) -> dict | None:
        """Read U8,U8,U16 output forcing array from two input registers."""
        regs = await self._read_registers(kind="input", slave=slave, address=address, count=2)
        if not regs or len(regs) != 2:
            return None
        return {
            "output_state": bool((int(regs[0]) >> 8) & 0xFF),
            "source": int(regs[0]) & 0xFF,
            "remaining_time_s": int(regs[1]),
        }

    async def write_u8_u8_u16_command(self, slave: int, address: int, first_u8: int, second_u8: int, value_u16: int) -> bool:
        """Write a U8,U8,U16 command packed into two registers."""
        first_reg = ((int(first_u8) & 0xFF) << 8) | (int(second_u8) & 0xFF)
        second_reg = int(value_u16) & 0xFFFF
        async with self._io_lock:
            client = self.client
            if client is None:
                return False

            values = [first_reg, second_reg]
            try:
                result = await client.write_registers(
                    address=address,
                    values=values,
                    device_id=slave,
                )
            except Exception as err:  # noqa: BLE001
                _LOGGER.debug(
                    "U8,U8,U16 command write exception slave=%s address=%s values=%s err=%r",
                    slave,
                    address,
                    values,
                    err,
                )
                return False

            ok = self._write_result_ok(result)
            _LOGGER.debug(
                "U8,U8,U16 command write result slave=%s address=%s values=%s ok=%s result=%r",
                slave,
                address,
                values,
                ok,
                result,
            )
            return ok

    async def write_uint16_command(self, slave: int, address: int, value: int) -> bool:
        """Write a single command register without automatic replay."""
        return await self.write_uint16(slave=slave, address=address, value=value)

    async def write_float32(self, slave: int, address: int, value: float) -> bool:
        """Write a 32-bit IEEE float to two holding registers."""
        regs = list(struct.unpack(">HH", struct.pack(">f", float(value))))
        async with self._io_lock:
            client = self.client
            if client is None:
                return False

            try:
                result = await client.write_registers(
                    address=address,
                    values=regs,
                    device_id=slave,
                )
            except Exception as err:  # noqa: BLE001
                _LOGGER.debug(
                    "float32 write exception slave=%s address=%s value=%s err=%r",
                    slave,
                    address,
                    value,
                    err,
                )
                return False

            ok = self._write_result_ok(result)
            _LOGGER.debug(
                "float32 write result slave=%s address=%s value=%s regs=%s ok=%s result=%r",
                slave,
                address,
                value,
                regs,
                ok,
                result,
            )
            return ok

    def _decode_ascii(self, regs: list[int] | None) -> str | None:
        if not regs:
            return None
        try:
            chars: list[str] = []
            for reg in regs:
                chars.append(chr((reg >> 8) & 0xFF))
                chars.append(chr(reg & 0xFF))
            value = "".join(chars).replace("\x00", "").strip()
            value = "".join(ch for ch in value if 32 <= ord(ch) <= 126)
            return value or None
        except Exception:
            return None
