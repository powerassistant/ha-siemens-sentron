"""Slave discovery for Siemens SENTRON."""

from __future__ import annotations

import asyncio
import logging
import re

from .const import (
    ARTICLE_NUMBER_VARIANT_HINTS,
    DEFAULT_SCAN_END,
    DEFAULT_SCAN_START,
    DEVICE_VARIANT_MAP,
    GATEWAY_POC1000_PAIRING_STATUS_BASE,
    GATEWAY_POC1000_CONNECTION_STATE_BASE,
    GATEWAY_POC1100_CONNECTION_STATE_BASE,
    GATEWAY_SLAVE,
    DISCOVERY_RETRIES,
    DISCOVERY_RETRY_DELAY,
    INVALID_VARIANTS,
    REGISTER_ARTICLE_NUMBER,
    REGISTER_ATTACHED_DEVICE_TYPE,
    REGISTER_DEVICE_FIRMWARE,
    REGISTER_DEVICE_VARIANT,
)
from .device_types import is_powercenter_1100_or_2000
from .modbus_api import SentronModbusApi

_LOGGER = logging.getLogger(__name__)

# Discovery order:
# 1) Gateway connection-state is the presence indicator. If a gateway slot reports
#    Connected, the slot is discovered even if the end-device variant register is
#    0/unknown or temporarily not readable.
# 2) Device Variant is authoritative when it is known/supported.
# 3) If Device Variant is 0/unknown/unreadable, use the article/order number at
#    register 3 (Modbus address 2, offset -1) as type fallback.
# 4) Attached Device Type is read only for diagnostics; it is not used as type fallback.
# 5) For debugging, gateway-connected slots that cannot be identified are still
#    created as generic SENTRON devices.


def _is_valid_variant(value: int | None) -> bool:
    if value is None:
        return False
    if value in INVALID_VARIANTS:
        return False
    mapped = DEVICE_VARIANT_MAP.get(value)
    if mapped is None:
        return False
    return mapped.get("device_type") != "unknown"


def _is_debug_unknown_variant(value: int | None) -> bool:
    return value == 0


def _normalize_article_number(value: str | None) -> str | None:
    if not value:
        return None
    normalized = re.sub(r"[^0-9A-Z]", "", value.upper())
    return normalized or None


def _variant_from_article_number(article_number: str | None) -> int | None:
    normalized = _normalize_article_number(article_number)
    if not normalized:
        return None

    # Longest hint first, so more specific patterns such as 5SL60 win over 5SL6.
    for hint, variant in sorted(
        ARTICLE_NUMBER_VARIANT_HINTS.items(), key=lambda item: len(item[0]), reverse=True
    ):
        if normalized.startswith(hint) or hint in normalized:
            if _is_valid_variant(variant):
                return variant
    return None


def _build_slave_metadata(slave: int, variant: int, article_number: str | None = None) -> dict:
    mapped = DEVICE_VARIANT_MAP.get(variant)

    if mapped is None or mapped.get("device_type") == "unknown":
        label_suffix = f" ({article_number})" if article_number else ""
        type_label = f"Unknown Variant {variant}{label_suffix}"
        return {
            "device_type": "generic_sentron_device",
            "type_label": type_label,
            "model": f"SENTRON {type_label}",
            "name": f"{slave} - {type_label}",
        }

    type_label = mapped["model"]
    return {
        "device_type": mapped["device_type"],
        "type_label": type_label,
        "model": f"SENTRON {type_label}",
        "name": f"{slave} - {type_label}",
    }


async def _read_article_number(modbus: SentronModbusApi, slave: int) -> str | None:
    # Register 3 in the Siemens map is address 2 after the project-wide offset -1.
    # Read a generous ASCII block; decoding strips NUL/padding in modbus_api.
    return await modbus.read_holding_string(
        slave=slave,
        address=REGISTER_ARTICLE_NUMBER,
        count=16,
    )


async def _resolve_variant_with_fallback(
    modbus: SentronModbusApi,
    slave: int,
    variant: int | None,
    *,
    gateway_connected: bool = False,
) -> tuple[int | None, int | None, str | None, str]:
    """Resolve the effective device variant for one discovered slave."""
    if _is_valid_variant(variant):
        return variant, None, None, "device_variant"

    attached_device_type = await modbus.read_holding_u16(
        slave=slave,
        address=REGISTER_ATTACHED_DEVICE_TYPE,
    )
    article_number = await _read_article_number(modbus, slave)
    article_variant = _variant_from_article_number(article_number)

    if _is_valid_variant(article_variant):
        _LOGGER.info(
            "Slave %s per Artikelnummer-Fallback erkannt: device_variant=%s article_number=%r -> effective_variant=%s",
            slave,
            variant,
            article_number,
            article_variant,
        )
        return article_variant, attached_device_type, article_number, "article_number"

    if _is_debug_unknown_variant(variant):
        _LOGGER.warning(
            "Slave %s wird als Debug-Unknown angelegt: device_variant=0 article_number=%r attached_device_type=%s",
            slave,
            article_number,
            attached_device_type,
        )
        return 0, attached_device_type, article_number, "debug_unknown_variant_0"

    if gateway_connected:
        _LOGGER.warning(
            "Slave %s wird wegen Gateway-Verbindungsstatus Connected als Debug-Unknown angelegt: device_variant=%s article_number=%r attached_device_type=%s",
            slave,
            variant,
            article_number,
            attached_device_type,
        )
        return 0, attached_device_type, article_number, "gateway_connected_unknown"

    _LOGGER.info(
        "Slave %s wird nicht angelegt: gateway_connected=%s device_variant=%s article_number=%r attached_device_type=%s unbekannt/unsupported",
        slave,
        gateway_connected,
        variant,
        article_number,
        attached_device_type,
    )
    return None, attached_device_type, article_number, "unknown"



def _gateway_connection_address(gateway: dict | None, slave: int) -> int | None:
    """Return gateway-side connection-state register address for one end-device slot."""
    if gateway is None:
        return None
    index = max(slave - 1, 0)
    if is_powercenter_1100_or_2000(gateway):
        return GATEWAY_POC1100_CONNECTION_STATE_BASE + index
    return GATEWAY_POC1000_CONNECTION_STATE_BASE + index


async def _read_gateway_connection_state(
    modbus: SentronModbusApi,
    gateway: dict | None,
    slave: int,
) -> int | None:
    address = _gateway_connection_address(gateway, slave)
    if address is None:
        return None
    return await modbus.read_input_u16(GATEWAY_SLAVE, address)


def _gateway_pairing_address(gateway: dict | None, slave: int) -> int | None:
    """Return POC1000 pairing-status address for end-device discovery."""
    if gateway is None or is_powercenter_1100_or_2000(gateway):
        return None
    return GATEWAY_POC1000_PAIRING_STATUS_BASE + max(slave - 1, 0)


async def _read_gateway_pairing_state(
    modbus: SentronModbusApi,
    gateway: dict | None,
    slave: int,
) -> int | None:
    address = _gateway_pairing_address(gateway, slave)
    if address is None:
        return None
    return await modbus.read_input_u16(GATEWAY_SLAVE, address)


async def async_discover_slaves(modbus: SentronModbusApi, gateway: dict | None = None) -> list[dict]:
    found: list[dict] = []

    for attempt in range(1, DISCOVERY_RETRIES + 1):
        _LOGGER.info(
            "Siemens SENTRON Discovery-Durchlauf %s/%s",
            attempt,
            DISCOVERY_RETRIES,
        )

        found.clear()

        for slave in range(DEFAULT_SCAN_START, DEFAULT_SCAN_END + 1):
            gateway_connection_state = await _read_gateway_connection_state(modbus, gateway, slave)
            gateway_pairing_state = await _read_gateway_pairing_state(modbus, gateway, slave)

            if gateway is not None and is_powercenter_1100_or_2000(gateway):
                gateway_connected = gateway_connection_state == 3
                slot_present = gateway_connected
            elif gateway is not None:
                # POC1000 discovery uses Pairing Status End Device 1..24.
                # Register decimals 1026..1049 become Modbus addresses 1025..1048.
                # Value 2 means "Pairing success" and is the presence indicator.
                gateway_connected = gateway_connection_state == 3
                slot_present = gateway_pairing_state == 2
            else:
                gateway_connected = False
                slot_present = True

            # Fast path: gateway-side status is now the presence indicator.
            # Disconnected/unpaired slots are skipped before any direct slave read, avoiding
            # slow Modbus timeouts on empty/offline slave addresses.
            if gateway is not None and not slot_present:
                _LOGGER.debug(
                    "Skip slave=%s: gateway_pairing_state=%s gateway_connection_state=%s is not present",
                    slave,
                    gateway_pairing_state,
                    gateway_connection_state,
                )
                continue

            raw_variant = await modbus.read_holding_u16(
                slave=slave,
                address=REGISTER_DEVICE_VARIANT,
            )
            variant, attached_device_type, article_number, detection_source = await _resolve_variant_with_fallback(
                modbus,
                slave,
                raw_variant,
                gateway_connected=gateway_connected,
            )

            valid_variant = _is_valid_variant(variant)
            debug_unknown = _is_debug_unknown_variant(variant)

            _LOGGER.info(
                "Probe slave=%s gateway_pairing_state=%s gateway_connection_state=%s gateway_connected=%s variant=%s raw_variant=%s article_number=%r attached_device_type=%s source=%s valid_variant=%s debug_unknown=%s",
                slave,
                gateway_pairing_state,
                gateway_connection_state,
                gateway_connected,
                variant,
                raw_variant,
                article_number,
                attached_device_type,
                detection_source,
                valid_variant,
                debug_unknown,
            )

            if variant is None or (not valid_variant and not debug_unknown):
                continue

            metadata = _build_slave_metadata(slave, variant, article_number)

            firmware = await modbus.read_holding_firmware_version(
                slave=slave,
                address=REGISTER_DEVICE_FIRMWARE,
                count=2,
            )

            found.append(
                {
                    "slave": slave,
                    "variant": variant,
                    "raw_variant": raw_variant,
                    "attached_device_type": attached_device_type,
                    "article_number": article_number,
                    "detection_source": detection_source,
                    "gateway_connection_state": gateway_connection_state,
                    "gateway_pairing_state": gateway_pairing_state,
                    "firmware": firmware or "Unknown",
                    "name": metadata["name"],
                    "device_type": metadata["device_type"],
                    "type_label": metadata["type_label"],
                    "model": metadata["model"],
                    "online": True,
                }
            )

        if found:
            _LOGGER.info(
                "Discovery erfolgreich: %s Gerät(e) gefunden: %s",
                len(found),
                [device["slave"] for device in found],
            )
            return found

        if attempt < DISCOVERY_RETRIES:
            _LOGGER.warning(
                "Discovery-Durchlauf %s fand keine Geräte. Warte %s Sekunden und versuche erneut.",
                attempt,
                DISCOVERY_RETRY_DELAY,
            )
            await asyncio.sleep(DISCOVERY_RETRY_DELAY)

    _LOGGER.error(
        "Discovery fehlgeschlagen: keine Geräte auf Slave %s-%s gefunden",
        DEFAULT_SCAN_START,
        DEFAULT_SCAN_END,
    )
    return []
