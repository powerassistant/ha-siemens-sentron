"""Root-device helper logic for Siemens SENTRON and VersiCharge."""

from __future__ import annotations

import logging

from .const import (
    GATEWAY_DISPLAY_ADDRESS,
    GATEWAY_POC1000_CONNECTION_STATE_BASE,
    GATEWAY_POC1000_PAIRING_STATUS_BASE,
    GATEWAY_SLAVE,
    GATEWAY_VARIANT_MAP,
    MANUFACTURER,
    PAC2200_IM0_ADDRESS,
    PAC2200_IM0_COUNT,
    PAC2200_ORDER_PREFIX,
    PAC2200_PROFILE_ID,
    PAC2200_SLAVE,
    REGISTER_DEVICE_VARIANT,
    REGISTER_GATEWAY_FIRMWARE,
    REGISTER_MANUFACTURER_ID,
    SIEMENS_MANUFACTURER_ID,
)
from .device_types import (
    DEVICE_KIND_PAC2200,
    DEVICE_KIND_POWERCENTER,
    DEVICE_KIND_VERSICHARGE,
    powercenter_type_from_variant,
)
from .modbus_api import SentronModbusApi
from .versicharge import (
    VERSICHARGE_DEFAULT_UNIT_ID,
    VERSICHARGE_FALLBACK_UNIT_ID,
    async_probe_versicharge,
)

_LOGGER = logging.getLogger(__name__)

_LEGACY_ROOT_DEVICE_PROBE_ORDER = (
    DEVICE_KIND_PAC2200,
    DEVICE_KIND_POWERCENTER,
    DEVICE_KIND_VERSICHARGE,
)
_VERSICHARGE_ROOT_DEVICE_PROBE_ORDER = (
    DEVICE_KIND_VERSICHARGE,
    DEVICE_KIND_PAC2200,
    DEVICE_KIND_POWERCENTER,
)


def _decode_ascii_words(words: list[int]) -> str:
    chars: list[str] = []
    for reg in words:
        chars.append(chr((int(reg) >> 8) & 0xFF))
        chars.append(chr(int(reg) & 0xFF))
    value = "".join(chars).replace("\x00", "").strip()
    return "".join(ch for ch in value if 32 <= ord(ch) <= 126).strip()


def _decode_pac2200_im0(regs: list[int] | None) -> dict | None:
    if not regs or len(regs) < PAC2200_IM0_COUNT:
        return None

    manufacturer_id = int(regs[0])
    order_id = _decode_ascii_words(regs[1:11])
    serial_number = _decode_ascii_words(regs[11:19])
    hardware_revision = int(regs[19])

    sw1 = int(regs[20])
    sw2 = int(regs[21])
    prefix = (sw1 >> 8) & 0xFF
    major = sw1 & 0xFF
    minor = (sw2 >> 8) & 0xFF
    patch = sw2 & 0xFF
    prefix_char = chr(prefix) if 32 <= prefix <= 126 else "V"
    firmware = f"{prefix_char}{major}.{minor}.{patch}"

    profile_id = int(regs[23])
    im_version = int(regs[25])
    im_supported = int(regs[26])

    if manufacturer_id != SIEMENS_MANUFACTURER_ID:
        return None
    if profile_id != PAC2200_PROFILE_ID:
        return None
    if order_id and not order_id.upper().startswith(PAC2200_ORDER_PREFIX):
        return None

    return {
        "manufacturer_id": manufacturer_id,
        "order_id": order_id,
        "serial_number": serial_number,
        "hardware_revision": hardware_revision,
        "firmware": firmware,
        "profile_id": profile_id,
        "im_version": im_version,
        "im_supported": im_supported,
        "raw_registers": regs,
    }


async def detect_pac2200(modbus: SentronModbusApi) -> dict | None:
    """Detect a directly connected PAC2200 via complete I&M0 block.

    PAC2200: slave 1, holding register 64001, count 27, no -1 offset.
    Important: read as one block; single field reads can fail on the PAC.
    """
    regs = await modbus.read_holding_registers(
        slave=PAC2200_SLAVE,
        address=PAC2200_IM0_ADDRESS,
        count=PAC2200_IM0_COUNT,
    )
    info = _decode_pac2200_im0(regs)
    if info:
        _LOGGER.info(
            "PAC2200 erkannt: slave=%s address=%s order_id=%s serial=%s firmware=%s profile_id=0x%04X",
            PAC2200_SLAVE,
            PAC2200_IM0_ADDRESS,
            info.get("order_id"),
            info.get("serial_number"),
            info.get("firmware"),
            info.get("profile_id"),
        )
    else:
        _LOGGER.debug(
            "PAC2200 I&M0 nicht erkannt: slave=%s address=%s count=%s regs=%s",
            PAC2200_SLAVE,
            PAC2200_IM0_ADDRESS,
            PAC2200_IM0_COUNT,
            regs,
        )
    return info


async def read_gateway_manufacturer_id(modbus: SentronModbusApi) -> int | None:
    for slave in (GATEWAY_SLAVE, 0):
        value = await modbus.read_input_u16(slave=slave, address=REGISTER_MANUFACTURER_ID)
        if value is not None:
            return value
        value = await modbus.read_holding_u16(slave=slave, address=REGISTER_MANUFACTURER_ID)
        if value is not None:
            return value
    return None


async def detect_gateway_variant(modbus: SentronModbusApi) -> int | None:
    """Read Powercenter device variant from slave 255 with offset -1 applied.

    This mirrors the end-device variant logic: the constant already contains
    the Modbus address after applying the Siemens register offset -1
    (Register 112 -> address 111), and the gateway itself is always queried
    via slave 255. Some Powercenter firmware exposes the value on holding
    registers, others answer more reliably on input registers, so holding is
    tried first and input is used only as fallback.
    """
    value = await modbus.read_holding_u16(
        slave=GATEWAY_SLAVE,
        address=REGISTER_DEVICE_VARIANT,
    )
    if value is not None:
        return value
    return await modbus.read_input_u16(
        slave=GATEWAY_SLAVE,
        address=REGISTER_DEVICE_VARIANT,
    )


def gateway_model_from_variant(variant: int | None) -> str:
    if variant in GATEWAY_VARIANT_MAP:
        return GATEWAY_VARIANT_MAP[variant]
    if variant is None or variant == 0:
        return "SENTRON Powercenter 1000"
    return f"Unbekanntes Siemens Gerät Variant {variant}"


async def detect_gateway_firmware(modbus: SentronModbusApi) -> str:
    for count in (2, 4):
        fw = await modbus.read_holding_firmware_version(slave=GATEWAY_SLAVE, address=REGISTER_GATEWAY_FIRMWARE, count=count)
        if fw:
            return fw.strip()
    return "Unknown"


async def probe_powercenter(modbus: SentronModbusApi) -> dict | None:
    """Return a validated Powercenter fingerprint, or ``None``.

    Powercenter 1100/2000 expose an explicit root variant. Powercenter 1000
    can report no variant, so it additionally has to expose both a readable
    firmware value and a gateway-side slot-status register. Manufacturer ID
    alone is deliberately insufficient to classify an arbitrary Siemens
    Modbus device as a Powercenter.
    """
    manufacturer_id = await read_gateway_manufacturer_id(modbus)
    if manufacturer_id != SIEMENS_MANUFACTURER_ID:
        return None

    variant = await detect_gateway_variant(modbus)
    if variant not in (None, 0, *GATEWAY_VARIANT_MAP):
        return None

    firmware = await detect_gateway_firmware(modbus)
    if variant in (None, 0):
        pairing_state = await modbus.read_input_u16(
            GATEWAY_SLAVE, GATEWAY_POC1000_PAIRING_STATUS_BASE
        )
        connection_state = await modbus.read_input_u16(
            GATEWAY_SLAVE, GATEWAY_POC1000_CONNECTION_STATE_BASE
        )
        if firmware == "Unknown" or (
            pairing_state is None and connection_state is None
        ):
            return None

    return {
        "manufacturer_id": manufacturer_id,
        "variant": variant,
        "firmware": firmware,
    }


def _versicharge_unit_ids(modbus_unit_id: int | None) -> tuple[int, ...]:
    """Return the configured VersiCharge unit and its documented fallback."""
    try:
        unit_id = int(modbus_unit_id)
    except (TypeError, ValueError):
        unit_id = VERSICHARGE_DEFAULT_UNIT_ID
    if not 1 <= unit_id <= 247:
        unit_id = VERSICHARGE_DEFAULT_UNIT_ID

    if (
        unit_id == VERSICHARGE_DEFAULT_UNIT_ID
        and VERSICHARGE_FALLBACK_UNIT_ID != VERSICHARGE_DEFAULT_UNIT_ID
    ):
        return (unit_id, VERSICHARGE_FALLBACK_UNIT_ID)
    return (unit_id,)


def _root_device_probe_order(
    device_kind: str | None,
    modbus_unit_id: int | None,
) -> tuple[str, ...]:
    """Prefer stored metadata and preserve probing for legacy entries."""
    probe_order = (
        _VERSICHARGE_ROOT_DEVICE_PROBE_ORDER
        if modbus_unit_id is not None
        else _LEGACY_ROOT_DEVICE_PROBE_ORDER
    )
    if device_kind not in probe_order:
        return probe_order
    return (device_kind,) + tuple(
        candidate
        for candidate in probe_order
        if candidate != device_kind
    )


async def async_detect_root_device(
    modbus: SentronModbusApi,
    *,
    device_kind: str | None = None,
    modbus_unit_id: int | None = None,
) -> tuple[str, int, dict] | None:
    """Detect a supported root, trying a stored device kind first."""
    for candidate in _root_device_probe_order(device_kind, modbus_unit_id):
        if candidate == DEVICE_KIND_PAC2200:
            info = await detect_pac2200(modbus)
            if info:
                return candidate, PAC2200_SLAVE, info
            continue

        if candidate == DEVICE_KIND_VERSICHARGE:
            unit_ids = _versicharge_unit_ids(modbus_unit_id)
            info = await async_probe_versicharge(
                modbus,
                unit_ids=unit_ids,
            )
            if info:
                unit_id = int(
                    info.get("unit_id")
                    or info.get("modbus_unit_id")
                    or unit_ids[0]
                )
                return candidate, unit_id, info
            continue

        info = await probe_powercenter(modbus)
        if info:
            return candidate, GATEWAY_SLAVE, info

    return None


def build_pac2200_gateway_data(*, entry_id: str, host: str, port: int, pac_info: dict) -> dict:
    model = "SENTRON PAC2200"
    return {
        "id": f"{entry_id}_pac2200",
        "name": f"1 - {model}",
        "manufacturer": MANUFACTURER,
        "manufacturer_id": pac_info.get("manufacturer_id"),
        "model": model,
        "host": host,
        "port": port,
        "firmware": pac_info.get("firmware") or "Unknown",
        "variant": "PAC2200",
        "online": True,
        "device_kind": DEVICE_KIND_PAC2200,
        "order_id": pac_info.get("order_id") or "PAC2200",
        "serial_number": pac_info.get("serial_number"),
        "hardware_revision": pac_info.get("hardware_revision"),
        "profile_id": pac_info.get("profile_id"),
        "im_version": pac_info.get("im_version"),
        "im_supported": pac_info.get("im_supported"),
    }


def build_versicharge_gateway_data(
    *,
    entry_id: str,
    host: str,
    port: int,
    unit_id: int,
    versicharge_info: dict,
) -> dict:
    """Build the root metadata while retaining all probed static values."""
    model = str(versicharge_info.get("model") or "").strip()
    if not model:
        model = "VersiCharge AC Series"
    serial_number = versicharge_info.get("serial_number")
    firmware = versicharge_info.get("a8_firmware") or "Unknown"

    return {
        **versicharge_info,
        "id": f"{entry_id}_versicharge",
        "name": f"{unit_id} - {model}",
        "manufacturer": MANUFACTURER,
        "model": model,
        "host": host,
        "port": port,
        "firmware": firmware,
        "serial_number": serial_number,
        "unit_id": unit_id,
        "modbus_unit_id": unit_id,
        "variant": "VersiCharge AC Series",
        "online": True,
        "device_kind": DEVICE_KIND_VERSICHARGE,
    }


async def async_build_gateway_data(
    modbus: SentronModbusApi,
    entry_id: str,
    host: str,
    port: int,
    name: str,
    device_kind: str | None = None,
    modbus_unit_id: int | None = None,
) -> dict:
    """Build root data for the detected Siemens Modbus device."""
    detection = await async_detect_root_device(
        modbus,
        device_kind=device_kind,
        modbus_unit_id=modbus_unit_id,
    )
    if detection is None:
        raise ValueError("The connected Modbus device is not supported")

    detected_kind, unit_id, device_info = detection
    if detected_kind == DEVICE_KIND_PAC2200:
        pac_data = build_pac2200_gateway_data(
            entry_id=entry_id,
            host=host,
            port=port,
            pac_info=device_info,
        )
        _LOGGER.info(
            "PAC2200 aufgebaut: name=%s model=%s manufacturer_id=%s order_id=%s firmware=%s host=%s port=%s",
            pac_data["name"], pac_data["model"], pac_data["manufacturer_id"], pac_data.get("order_id"), pac_data["firmware"], pac_data["host"], pac_data["port"],
        )
        return pac_data

    if detected_kind == DEVICE_KIND_VERSICHARGE:
        versicharge_data = build_versicharge_gateway_data(
            entry_id=entry_id,
            host=host,
            port=port,
            unit_id=unit_id,
            versicharge_info=device_info,
        )
        _LOGGER.info(
            "VersiCharge aufgebaut: name=%s model=%s serial=%s firmware=%s "
            "unit_id=%s host=%s port=%s",
            versicharge_data["name"],
            versicharge_data["model"],
            versicharge_data.get("serial_number"),
            versicharge_data["firmware"],
            versicharge_data["unit_id"],
            versicharge_data["host"],
            versicharge_data["port"],
        )
        return versicharge_data

    manufacturer_id = device_info["manufacturer_id"]
    variant = device_info["variant"]
    model = gateway_model_from_variant(variant)
    firmware = device_info["firmware"]
    gateway_name = f"{GATEWAY_DISPLAY_ADDRESS} - {model}"
    gateway_data = {
        "id": f"{entry_id}_gateway",
        "name": gateway_name,
        "manufacturer": MANUFACTURER,
        "manufacturer_id": manufacturer_id,
        "model": model,
        "host": host,
        "port": port,
        "firmware": firmware,
        "variant": variant,
        "online": True,
        "device_kind": DEVICE_KIND_POWERCENTER,
        "powercenter_type": powercenter_type_from_variant(variant),
    }
    _LOGGER.info(
        "Gateway aufgebaut: name=%s model=%s manufacturer_id=%s variant=%s firmware=%s host=%s port=%s",
        gateway_data["name"], gateway_data["model"], gateway_data["manufacturer_id"], gateway_data["variant"], gateway_data["firmware"], gateway_data["host"], gateway_data["port"],
    )
    return gateway_data
