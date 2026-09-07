"""Siemens VersiCharge AC Series Modbus data model.

All addresses in this module are zero-based Modbus PDU addresses.  Siemens'
external 4xxxx register references must never be passed to pymodbus directly.

The implementation supports the legacy A5E52200882-AF map and the current
A5E52200882-AL map.  Firmware 2.135 changed energy and power-factor scaling;
firmware 2.136 changed charger states and the error-code table.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from enum import StrEnum
from typing import Any, Final, Protocol


VERSICHARGE_DEFAULT_UNIT_ID: Final = 2
VERSICHARGE_FALLBACK_UNIT_ID: Final = 1
VERSICHARGE_MIN_CURRENT: Final = 6
VERSICHARGE_MAX_CURRENT: Final = 80
VERSICHARGE_POLL_INTERVAL_SECONDS: Final = 10
VERSICHARGE_MODBUS_TIMEOUT_SECONDS: Final = 5
VERSICHARGE_COMMAND_TIMEOUT_SECONDS: Final = 12
VERSICHARGE_COMMAND_INTERVAL_SECONDS: Final = 5
VERSICHARGE_NOMINAL_PHASE_VOLTAGE: Final = 230
VERSICHARGE_POWER_STEP_KW: Final = Decimal("0.1")

VERSICHARGE_CURRENT_REGISTER: Final = 1633
VERSICHARGE_FALLBACK_CURRENT_REGISTER: Final = 1660
VERSICHARGE_FALLBACK_TIME_REGISTER: Final = 1661

VERSICHARGE_LEGACY_MAP: Final = "A5E52200882-AF (09/2023)"
VERSICHARGE_CURRENT_MAP: Final = "A5E52200882-AL (02/2025)"
VERSICHARGE_MODERN_SCALING_FIRMWARE: Final = (2, 135)
VERSICHARGE_MODERN_STATE_FIRMWARE: Final = (2, 136)


class HoldingRegisterReader(Protocol):
    """Small protocol used by discovery and polling helpers."""

    async def read_holding_registers(
        self, slave: int, address: int, count: int
    ) -> list[int] | None:
        """Read holding registers."""


class RegisterKind(StrEnum):
    """Encodings used by the VersiCharge register map."""

    UINT16 = "uint16"
    INT16 = "int16"
    UINT32_BE = "uint32_be"
    ASCII = "ascii"
    PRODUCTION_DATE = "production_date"


@dataclass(frozen=True, slots=True)
class RegisterDefinition:
    """Definition of one logical value."""

    key: str
    address: int
    count: int = 1
    kind: RegisterKind = RegisterKind.UINT16


@dataclass(frozen=True, slots=True)
class VersiChargeSensorDescription:
    """Home Assistant-independent description of one root sensor."""

    key: str
    translation_key: str
    unit: str | None = None
    device_class: str | None = None
    state_class: str | None = None
    icon: str | None = None
    precision: int | None = None
    enabled_default: bool = True
    diagnostic: bool = False
    options: tuple[str, ...] | None = None


PLATFORM_TYPES: Final = {
    1: "residential",
    2: "commercial",
    3: "erk",
}

CONNECTIVITY_TYPES: Final = {
    0: "not_commissioned",
    1: "wifi",
    2: "cellular",
    3: "ethernet",
}

METER_TYPES: Final = {
    0: "none",
    1: "basic",
    2: "ansi",
    3: "mid",
    4: "integrated_mid",
    5: "erk",
    7: "cmc",
    9: "onboard_cmc",
    25: "blocked",
}

OUTLET_TYPES: Final = {
    0: "left_type_2_socket",
    1: "left_type_2_cable_7m",
    2: "left_type_2_shuttered_france",
    3: "left_type_1_cable_7m",
    4: "left_gbt_cable_6m",
    5: "front_j1772_20ft",
    6: "front_j1772_25ft",
    7: "right_type_2_socket",
    8: "right_type_2_cable_7m",
    9: "right_shuttered_e_plug",
    10: "right_type_1_cable_7m",
    11: "right_shuttered_f_plug",
    12: "right_shuttered_cover",
    13: "reserved_13",
    14: "dual_type_2_sockets",
    15: "dual_type_2_cables_7m",
    16: "dual_type_2_france_7m",
    17: "dual_type_1_cables_7m",
    18: "dual_gbt_cables_7m",
    19: "ccs1_j1772_25ft",
    20: "reserved_20",
    21: "reserved_21",
    22: "blocked",
}

OCPP_STATES: Final = {
    1: "available",
    2: "preparing",
    3: "charging",
    4: "suspended_ev",
    5: "suspended_evse",
    6: "faulted",
    7: "finishing",
    8: "unavailable",
}

LEGACY_ERROR_CODES: Final = {
    0: "no_fault",
    1: "any_line_phase_under_voltage",
    2: "line_phase_a_under_voltage",
    3: "line_phase_b_under_voltage",
    4: "line_phase_c_under_voltage",
    5: "any_line_phase_over_voltage",
    6: "line_phase_a_over_voltage",
    7: "line_phase_b_over_voltage",
    8: "line_phase_c_over_voltage",
    9: "any_line_phase_zero_voltage",
    10: "line_phase_a_zero_voltage",
    11: "line_phase_b_zero_voltage",
    12: "line_phase_c_zero_voltage",
    13: "any_load_phase_under_voltage",
    14: "load_phase_a_under_voltage",
    15: "load_phase_b_under_voltage",
    16: "load_phase_c_under_voltage",
    17: "any_load_phase_over_voltage",
    18: "load_phase_a_over_voltage",
    19: "load_phase_b_over_voltage",
    20: "load_phase_c_over_voltage",
    21: "any_load_phase_zero_voltage",
    22: "load_phase_a_zero_voltage",
    23: "load_phase_b_zero_voltage",
    24: "load_phase_c_zero_voltage",
    25: "bad_pilot_voltage",
    26: "bad_amp_switch_position",
    27: "adc_fault",
    28: "static_memory_fault",
    29: "ccid_fault",
    30: "ccid_self_test_fault",
    31: "contactor_open",
    32: "over_temperature",
    33: "j1772_communication_fault",
    34: "sgd_communication_fault",
}

MODERN_ERROR_CODES: Final = {
    0: "no_fault",
    1: "reserved",
    2: "line_phase_a_under_voltage",
    3: "line_phase_b_under_voltage",
    4: "line_phase_c_under_voltage",
    5: "reserved",
    6: "line_phase_a_over_voltage",
    7: "line_phase_b_over_voltage",
    8: "line_phase_c_over_voltage",
    9: "reserved",
    10: "line_phase_a_zero_voltage",
    11: "line_phase_b_zero_voltage",
    12: "line_phase_c_zero_voltage",
    **{code: "reserved" for code in range(13, 22)},
    22: "load_phase_a_zero_voltage",
    23: "load_phase_b_zero_voltage",
    24: "load_phase_c_zero_voltage",
    25: "bad_pilot_voltage",
    26: "bad_amp_switch_position",
    27: "adc_fault",
    28: "static_memory_fault",
    29: "ccid_fault",
    30: "ccid_self_test_fault",
    31: "reserved",
    32: "reserved",
    33: "reserved",
    34: "reserved",
    35: "eeprom_read_write_fault",
    36: "fram_read_write_fault",
    37: "metering_chip_read_write_fault",
    38: "ccid_close_on_fault",
    39: "reserved",
    40: "connector_lock_fault",
    41: "cable_max_temperature_fault",
    42: "welded_contact_phase_a_fault",
    43: "welded_contact_phase_b_fault",
    44: "welded_contact_phase_c_fault",
    45: "diode_fault",
    46: "ground_monitoring_fault",
    47: "onboard_temperature_fault",
    48: "over_current_fault",
    49: "onboard_temperature_ntca_fault",
    50: "onboard_temperature_ntca_ntcb_fault",
    51: "onboard_temperature_ntcb_fault",
    52: "cable_temperature_ptca_fault",
    53: "cable_temperature_ptca_ptcb_fault",
    54: "cable_temperature_ptcb_fault",
}

MODERN_RECOVERABLE_ERRORS: Final = {
    2,
    3,
    4,
    6,
    7,
    8,
    10,
    11,
    12,
    25,
    35,
    36,
    37,
    46,
    47,
    49,
    50,
    51,
    52,
    53,
    54,
}


STATIC_REGISTERS: Final = (
    RegisterDefinition("manufacturer", 0, 5, RegisterKind.ASCII),
    RegisterDefinition("production_date", 5, 2, RegisterKind.PRODUCTION_DATE),
    RegisterDefinition("serial_number", 7, 5, RegisterKind.ASCII),
    RegisterDefinition("model", 12, 10, RegisterKind.ASCII),
    RegisterDefinition("platform_type_raw", 22),
    RegisterDefinition("number_of_outlets", 24),
    RegisterDefinition("outlet_type_raw", 25),
    RegisterDefinition("delay_setting_raw", 26),
    RegisterDefinition("connectivity_raw", 27),
    RegisterDefinition("rated_current", 28),
    RegisterDefinition("installation_current", 29),
    RegisterDefinition("meter_type_raw", 30),
    RegisterDefinition("a8_firmware", 31, 5, RegisterKind.ASCII),
    RegisterDefinition("m0_firmware", 36, 5, RegisterKind.ASCII),
    RegisterDefinition("modbus_app_version", 41),
    RegisterDefinition("firmware_variant", 42, 6, RegisterKind.ASCII),
    RegisterDefinition("firmware_release_date", 48, 3, RegisterKind.ASCII),
)

# Separate reads avoid the removed address 23 and optional-firmware holes.
STATIC_COMMON_BLOCKS: Final = (
    (0, 5),
    (5, 2),
    (7, 5),
    (12, 10),
    (22, 1),
    (24, 7),
    (31, 11),
)
STATIC_MODERN_BLOCKS: Final = ((42, 9),)

DYNAMIC_REGISTERS: Final = (
    RegisterDefinition("evse_state_raw", 1599, kind=RegisterKind.ASCII),
    RegisterDefinition("error_code", 1600, kind=RegisterKind.INT16),
    RegisterDefinition("ocpp_state_raw", 1601),
    RegisterDefinition("temperature_onboard_b", 1602, kind=RegisterKind.INT16),
    RegisterDefinition("temperature_offboard_a", 1603, kind=RegisterKind.INT16),
    RegisterDefinition("temperature_onboard_a", 1604, kind=RegisterKind.INT16),
    RegisterDefinition("temperature_offboard_b", 1605, kind=RegisterKind.INT16),
    RegisterDefinition("charging_current_limit", 1633),
    RegisterDefinition("session_energy_target_raw", 1640, 2, RegisterKind.UINT32_BE),
    RegisterDefinition("charger_phase_raw", 1642),
    RegisterDefinition("current_l1", 1647),
    RegisterDefinition("current_l2", 1648),
    RegisterDefinition("current_l3", 1649),
    RegisterDefinition("current_phase_sum", 1650),
    RegisterDefinition("voltage_l1_n", 1651),
    RegisterDefinition("voltage_l2_n", 1652),
    RegisterDefinition("voltage_l3_n", 1653),
    RegisterDefinition("voltage_l1_l2", 1654),
    RegisterDefinition("voltage_l2_l3", 1655),
    RegisterDefinition("voltage_l3_l1", 1656),
    RegisterDefinition("fallback_current", 1660),
    RegisterDefinition("fallback_time", 1661),
    # Real chargers can briefly return negative signed phase values despite
    # the UInt16 wording in some map revisions.  Signed decoding avoids 65 kW
    # spikes from values such as 0xFFE4 (-28 W).
    RegisterDefinition("active_power_l1", 1662, kind=RegisterKind.INT16),
    RegisterDefinition("active_power_l2", 1663, kind=RegisterKind.INT16),
    RegisterDefinition("active_power_l3", 1664, kind=RegisterKind.INT16),
    RegisterDefinition("active_power_total_reported", 1665, kind=RegisterKind.INT16),
    RegisterDefinition("power_factor_l1_raw", 1666),
    RegisterDefinition("power_factor_l2_raw", 1667),
    RegisterDefinition("power_factor_l3_raw", 1668),
    RegisterDefinition("power_factor_average_raw", 1669),
    RegisterDefinition("apparent_power_l1", 1670),
    RegisterDefinition("apparent_power_l2", 1671),
    RegisterDefinition("apparent_power_l3", 1672),
    RegisterDefinition("apparent_power_total", 1673),
    RegisterDefinition("reactive_power_l1", 1674, kind=RegisterKind.INT16),
    RegisterDefinition("reactive_power_l2", 1675, kind=RegisterKind.INT16),
    RegisterDefinition("reactive_power_l3", 1676, kind=RegisterKind.INT16),
    # Siemens declares the phase sum as UInt16 even though the three phase
    # detail registers immediately before it are signed Int16 values.
    RegisterDefinition("reactive_power_total", 1677),
    RegisterDefinition("energy_total_raw", 1692, 2, RegisterKind.UINT32_BE),
)

DYNAMIC_COMMON_BLOCKS: Final = (
    (1633, 1),
    (1640, 3),
    (1647, 10),
    (1660, 18),
    (1692, 2),
)
DYNAMIC_LEGACY_STATUS_BLOCKS: Final = ((1599, 4),)
DYNAMIC_MODERN_STATUS_BLOCKS: Final = ((1599, 7),)


def decode_ascii(words: list[int]) -> str:
    """Decode Siemens' big-byte-first ASCII words."""
    raw = b"".join((int(word) & 0xFFFF).to_bytes(2, "big") for word in words)
    text = raw.decode("ascii", errors="ignore").replace("\x00", "").strip()
    return "".join(char for char in text if 32 <= ord(char) <= 126).strip()


def decode_int16(word: int) -> int | None:
    """Decode a signed word while treating 0xFFFF as unavailable."""
    word = int(word) & 0xFFFF
    if word == 0xFFFF:
        return None
    return word - 0x10000 if word & 0x8000 else word


def decode_uint16(word: int) -> int | None:
    """Decode an unsigned word while treating 0xFFFF as unavailable."""
    word = int(word) & 0xFFFF
    return None if word == 0xFFFF else word


def decode_uint32_be(words: list[int]) -> int | None:
    """Decode the documented high-word-first UInt32 representation."""
    if len(words) != 2:
        raise ValueError("UInt32 requires exactly two registers")
    value = ((int(words[0]) & 0xFFFF) << 16) | (int(words[1]) & 0xFFFF)
    return None if value == 0xFFFFFFFF else value


def decode_register(definition: RegisterDefinition, words: list[int]) -> Any:
    """Decode one register definition."""
    if len(words) != definition.count:
        raise ValueError(
            f"{definition.key} requires {definition.count} registers, got {len(words)}"
        )
    if definition.kind is RegisterKind.ASCII:
        return decode_ascii(words) or None
    if definition.kind is RegisterKind.INT16:
        return decode_int16(words[0])
    if definition.kind is RegisterKind.UINT32_BE:
        return decode_uint32_be(words)
    if definition.kind is RegisterKind.PRODUCTION_DATE:
        year = decode_uint16(words[0])
        if year is None:
            return None
        month = (int(words[1]) >> 8) & 0xFF
        day = int(words[1]) & 0xFF
        try:
            return date(year, month, day).isoformat()
        except ValueError:
            return None
    return decode_uint16(words[0])


def decode_definitions(
    definitions: tuple[RegisterDefinition, ...], blocks: dict[int, list[int]]
) -> dict[str, Any]:
    """Decode every definition covered by a successfully read block."""
    decoded: dict[str, Any] = {}
    for definition in definitions:
        for start, words in blocks.items():
            offset = definition.address - start
            if offset >= 0 and offset + definition.count <= len(words):
                decoded[definition.key] = decode_register(
                    definition, words[offset : offset + definition.count]
                )
                break
    return decoded


def firmware_tuple(value: str | None) -> tuple[int, ...]:
    """Parse a version such as ``V2.136.14`` or ``2.135.12-XXX``."""
    if not value:
        return ()
    parts: list[int] = []
    for part in value.strip().lstrip("Vv").split("."):
        digits = ""
        for char in part:
            if not char.isdigit():
                break
            digits += char
        if not digits:
            break
        parts.append(int(digits))
    return tuple(parts)


def register_profile(
    firmware: str | None, *, modern_registers_present: bool = False
) -> str:
    """Return ``legacy``, ``modern`` or a safe modern assumption."""
    version = firmware_tuple(firmware)
    if version:
        return (
            "modern"
            if version >= VERSICHARGE_MODERN_SCALING_FIRMWARE
            else "legacy"
        )
    return "modern" if modern_registers_present else "modern_assumed"


def uses_modern_scaling(profile: str) -> bool:
    """Return whether current-map scaling must be used."""
    return profile != "legacy"


def normalize_charging_current_readback(
    raw_value: int | None, *, profile: str
) -> float | None:
    """Normalize both documented and firmware-echo current readbacks.

    Siemens documents a whole-ampere value from register 1633 even after a
    centiampere command (for example, writing 750 should read back as 8 A).
    Some firmware may instead echo the written 0.01-A representation.  Accept
    both forms while rejecting values outside the documented 0..80-A range.
    """
    if not isinstance(raw_value, int):
        return None
    if 0 <= raw_value <= VERSICHARGE_MAX_CURRENT:
        return float(raw_value)
    if uses_modern_scaling(profile) and 101 <= raw_value <= 8000:
        return round(raw_value / 100, 2)
    return None


def encode_charging_current(current_a: int) -> int:
    """Encode one unambiguous whole-ampere command for register 1633.

    Both Siemens register-map generations accept values up to 80 directly in
    amperes.  Deliberately not using the modern 0.01-A representation makes the
    command independent of firmware-specific coarse readback behaviour.
    """
    current = float(current_a)
    if current == 0:
        return 0
    if not VERSICHARGE_MIN_CURRENT <= current <= VERSICHARGE_MAX_CURRENT:
        raise ValueError(
            f"Charging current must be 0 or {VERSICHARGE_MIN_CURRENT}.."
            f"{VERSICHARGE_MAX_CURRENT} A"
        )
    if not current.is_integer():
        raise ValueError("VersiCharge control uses whole amperes only")
    return int(current)


def quantize_power_kw(value: float) -> float:
    """Return a finite positive kW target rounded half-up to one decimal."""
    try:
        numeric = Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError) as err:
        raise ValueError("Charging power must be numeric") from err
    if not numeric.is_finite() or numeric <= 0:
        raise ValueError("Use the charging switch to pause the charger")
    return float(numeric.quantize(VERSICHARGE_POWER_STEP_KW, rounding=ROUND_HALF_UP))


def nominal_power_kw_for_current(current_a: int, phase_count: int) -> float:
    """Return nominal active power for a whole-ampere command."""
    if phase_count not in {1, 3}:
        raise ValueError("The charger phase mode is unavailable")
    current = encode_charging_current(current_a)
    power = (
        Decimal(current)
        * Decimal(VERSICHARGE_NOMINAL_PHASE_VOLTAGE)
        * Decimal(phase_count)
        / Decimal(1000)
    )
    return float(power.quantize(VERSICHARGE_POWER_STEP_KW, rounding=ROUND_HALF_UP))


def nominal_power_bounds_kw(
    values: dict[str, Any], installation_current_a: int
) -> tuple[float, float] | None:
    """Return stable 0.1-kW input bounds for the effective phase count."""
    phases = active_phase_count(values)
    if phases is None:
        return None
    return (
        nominal_power_kw_for_current(VERSICHARGE_MIN_CURRENT, phases),
        nominal_power_kw_for_current(int(installation_current_a), phases),
    )


def whole_amp_current_for_power_kw(
    power_kw: float,
    values: dict[str, Any],
    installation_current_a: int,
) -> int:
    """Convert a 0.1-kW target once using nominal voltage and whole amperes."""
    power = Decimal(str(quantize_power_kw(power_kw)))
    phases = active_phase_count(values)
    if phases is None:
        raise ValueError("The charger phase mode is unavailable")

    bounds = nominal_power_bounds_kw(values, installation_current_a)
    if bounds is None:
        raise ValueError("The charger phase mode is unavailable")
    minimum, maximum = bounds
    if not Decimal(str(minimum)) <= power <= Decimal(str(maximum)):
        raise ValueError(
            f"Charging power must be {minimum:.1f}..{maximum:.1f} kW"
        )

    denominator = Decimal(VERSICHARGE_NOMINAL_PHASE_VOLTAGE * phases)
    current = int(
        (power * Decimal(1000) / denominator).quantize(
            Decimal("1"), rounding=ROUND_HALF_UP
        )
    )
    if not VERSICHARGE_MIN_CURRENT <= current <= int(installation_current_a):
        raise ValueError(
            f"Charging power resolves outside {VERSICHARGE_MIN_CURRENT}.."
            f"{int(installation_current_a)} A"
        )
    return current


def active_phase_count(values: dict[str, Any]) -> int | None:
    """Return the stable charger phase type used for setpoint conversion."""
    effective = values.get("effective_phase_count")
    if effective in {1, 3}:
        return int(effective)

    raw = values.get("charger_phase_raw")
    if raw == 0:
        return 1
    if raw == 1:
        return 3
    return None


def power_per_amp(values: dict[str, Any], phase_count: int) -> float:
    """Return W/A from per-phase voltage and power-factor measurements."""
    phase_names = ("l1",) if phase_count == 1 else ("l1", "l2", "l3")
    total = 0.0
    for phase in phase_names:
        voltage = values.get(f"voltage_{phase}_n")
        if not isinstance(voltage, (int, float)) or not 100 <= float(voltage) <= 300:
            voltage = 230.0
        factor = values.get(f"power_factor_{phase}")
        if not isinstance(factor, (int, float)) or not 0.8 <= float(factor) <= 1.0:
            factor = 1.0
        total += float(voltage) * float(factor)
    return total


def power_for_current(current_a: float, values: dict[str, Any]) -> float | None:
    """Estimate active charging power for a current setpoint."""
    phases = active_phase_count(values)
    if phases is None:
        return None
    return float(current_a) * power_per_amp(values, phases)


def _map_value(mapping: dict[int, str], value: Any) -> str | None:
    if not isinstance(value, int):
        return None
    # Enum sensor states must always be one of the declared Home Assistant
    # options.  Keep the numeric source register available as a diagnostic
    # value instead of leaking arbitrary ``unknown_<number>`` states.
    return mapping.get(value, "unknown")


def _evse_state(raw: str | None) -> str | None:
    if not raw:
        return None
    value = raw.strip().upper()
    if value in {"A", "A1", "A2"}:
        return "not_connected"
    if value in {"B", "B1", "B2"}:
        return "connected"
    if value in {"C", "C1", "C2"}:
        return "charging"
    if value == "E":
        return "recoverable_fault"
    if value == "F":
        return "non_recoverable_fault"
    return "unknown"


def decode_static_values(blocks: dict[int, list[int]], unit_id: int) -> dict[str, Any]:
    """Decode identification, configuration and firmware data."""
    values = decode_definitions(STATIC_REGISTERS, blocks)
    values["platform_type"] = _map_value(
        PLATFORM_TYPES, values.get("platform_type_raw")
    )
    values["outlet_type"] = _map_value(
        OUTLET_TYPES, values.get("outlet_type_raw")
    )
    values["connectivity"] = _map_value(
        CONNECTIVITY_TYPES, values.get("connectivity_raw")
    )
    values["meter_type"] = _map_value(METER_TYPES, values.get("meter_type_raw"))

    delay = values.get("delay_setting_raw")
    values["delay_setting"] = (
        "off"
        if delay == 0
        else f"{delay}_hours"
        if delay in {2, 4, 6, 8}
        else "unknown"
        if isinstance(delay, int)
        else None
    )

    modern_registers_present = 42 in blocks
    profile = register_profile(
        values.get("a8_firmware"),
        modern_registers_present=modern_registers_present,
    )
    values["register_profile"] = profile
    version = firmware_tuple(values.get("a8_firmware"))
    values["state_profile"] = (
        "modern"
        if version >= VERSICHARGE_MODERN_STATE_FIRMWARE
        else "legacy"
        if version
        else "modern_assumed"
    )
    values["register_map"] = (
        VERSICHARGE_LEGACY_MAP if profile == "legacy" else VERSICHARGE_CURRENT_MAP
    )
    values["modbus_unit_id"] = unit_id
    return values


def decode_dynamic_values(
    blocks: dict[int, list[int]], *, profile: str, state_profile: str | None = None
) -> dict[str, Any]:
    """Decode live data and apply firmware-dependent semantics."""
    values = decode_definitions(DYNAMIC_REGISTERS, blocks)

    raw_current_limit = values.get("charging_current_limit")
    values["charging_current_limit_raw"] = raw_current_limit
    values["charging_current_limit"] = normalize_charging_current_readback(
        raw_current_limit, profile=profile
    )

    raw_state = values.get("evse_state_raw")
    values["evse_state"] = _evse_state(raw_state)

    ocpp_raw = values.get("ocpp_state_raw")
    values["ocpp_state"] = _map_value(OCPP_STATES, ocpp_raw)

    error_code = values.get("error_code")
    firmware_modern_state = (state_profile or profile) != "legacy"
    error_map = MODERN_ERROR_CODES if firmware_modern_state else LEGACY_ERROR_CODES
    values["error"] = _map_value(error_map, error_code)
    values["error_recoverable"] = (
        error_code in MODERN_RECOVERABLE_ERRORS
        if firmware_modern_state and isinstance(error_code, int)
        else None
    )

    phase = values.get("charger_phase_raw")
    values["charger_phase"] = (
        "single_phase"
        if phase == 0
        else "three_phase"
        if phase == 1
        else "unknown"
        if isinstance(phase, int)
        else None
    )

    pf_scale = 0.001 if uses_modern_scaling(profile) else 0.01
    for suffix in ("l1", "l2", "l3", "average"):
        raw = values.get(f"power_factor_{suffix}_raw")
        values[f"power_factor_{suffix}"] = (
            round(raw * pf_scale, 3) if isinstance(raw, int) else None
        )

    phase_powers = [
        values.get("active_power_l1"),
        values.get("active_power_l2"),
        values.get("active_power_l3"),
    ]
    valid_phase_powers = [value for value in phase_powers if isinstance(value, int)]
    reported = values.get("active_power_total_reported")
    total = sum(valid_phase_powers) if valid_phase_powers else reported
    # This is an appliance-consumption sensor.  Small negative transients are
    # measurement noise and must not become negative consumption statistics.
    values["active_power_total"] = max(0, total) if isinstance(total, int) else None

    energy_raw = values.get("energy_total_raw")
    energy_scale_kwh = 0.001 if uses_modern_scaling(profile) else 0.0001
    values["energy_total"] = (
        round(energy_raw * energy_scale_kwh, 4)
        if isinstance(energy_raw, int)
        else None
    )
    return values


async def _async_read_blocks(
    modbus: HoldingRegisterReader,
    unit_id: int,
    blocks: tuple[tuple[int, int], ...],
) -> dict[int, list[int]]:
    """Read documented blocks independently and retain successful responses."""
    result: dict[int, list[int]] = {}
    for address, count in blocks:
        registers = await modbus.read_holding_registers(
            slave=unit_id, address=address, count=count
        )
        if registers is not None and len(registers) == count:
            result[address] = registers
    return result


async def async_read_versicharge_static(
    modbus: HoldingRegisterReader, unit_id: int
) -> dict[str, Any]:
    """Read static data without crossing firmware-dependent holes."""
    blocks = await _async_read_blocks(modbus, unit_id, STATIC_COMMON_BLOCKS)
    if not blocks:
        # Do not manufacture a ``modern_assumed`` profile from a complete
        # timeout.  Callers can retain their last verified static snapshot.
        return {}
    provisional = decode_static_values(blocks, unit_id)
    if provisional.get("register_profile") != "legacy":
        blocks.update(
            await _async_read_blocks(modbus, unit_id, STATIC_MODERN_BLOCKS)
        )
    return decode_static_values(blocks, unit_id)


async def async_probe_versicharge(
    modbus: HoldingRegisterReader,
    unit_ids: tuple[int, ...] = (
        VERSICHARGE_DEFAULT_UNIT_ID,
        VERSICHARGE_FALLBACK_UNIT_ID,
    ),
) -> dict[str, Any] | None:
    """Identify a VersiCharge without mistaking another Siemens device for it."""
    seen: set[int] = set()
    for unit_id in unit_ids:
        if unit_id in seen or not 1 <= unit_id <= 247:
            continue
        seen.add(unit_id)

        manufacturer_words = await modbus.read_holding_registers(
            slave=unit_id, address=0, count=5
        )
        if not manufacturer_words:
            continue
        manufacturer = decode_ascii(manufacturer_words)
        if manufacturer.casefold() != "siemens ag":
            continue

        values = await async_read_versicharge_static(modbus, unit_id)
        model = str(values.get("model") or "").upper()
        explicit_family_marker = model.startswith("8EM") or "VERSICHARGE" in model
        plausible_fields = sum(
            (
                values.get("platform_type_raw") in PLATFORM_TYPES,
                values.get("number_of_outlets") in {1, 2},
                isinstance(values.get("rated_current"), int)
                and VERSICHARGE_MIN_CURRENT
                <= values["rated_current"]
                <= VERSICHARGE_MAX_CURRENT,
                isinstance(values.get("installation_current"), int)
                and VERSICHARGE_MIN_CURRENT
                <= values["installation_current"]
                <= VERSICHARGE_MAX_CURRENT,
            )
        )
        if not explicit_family_marker and plausible_fields < 3:
            continue

        values["manufacturer"] = manufacturer
        values["unit_id"] = unit_id
        return values
    return None


async def async_read_versicharge_values(
    modbus: HoldingRegisterReader,
    unit_id: int,
    *,
    profile: str,
    state_profile: str | None = None,
) -> dict[str, Any]:
    """Read all safe live-data blocks for one firmware profile."""
    status_blocks = (
        DYNAMIC_LEGACY_STATUS_BLOCKS
        if (state_profile or profile) == "legacy"
        else DYNAMIC_MODERN_STATUS_BLOCKS
    )
    blocks = await _async_read_blocks(
        modbus, unit_id, status_blocks + DYNAMIC_COMMON_BLOCKS
    )
    if not blocks:
        raise ValueError("No VersiCharge telemetry registers answered")
    return decode_dynamic_values(
        blocks, profile=profile, state_profile=state_profile
    )


@dataclass(slots=True)
class TotalEnergyFilter:
    """Suppress isolated zero/decrease glitches in a cumulative energy value."""

    confirmations: int = 3
    accepted: float | None = None
    _lower_count: int = 0
    _lower_last: float | None = None

    def seed(self, value: float | None) -> None:
        """Seed a higher recorder-restored value after an integration reload."""
        if value is None:
            return
        value = float(value)
        if value < 0:
            return
        if self.accepted is None or value > self.accepted:
            self.accepted = value
            self._lower_count = 0
            self._lower_last = None

    def update(self, value: float | None) -> float | None:
        """Return the stable value, accepting a real reset after confirmations."""
        if value is None:
            # A cumulative meter can safely retain its last accepted value
            # across a missed register block.  Besides avoiding a spurious
            # unavailable/reset transition, this also preserves useful native
            # restore data if Home Assistant stops during that transient.
            return self.accepted
        value = float(value)
        if self.accepted is None or value >= self.accepted:
            self.accepted = value
            self._lower_count = 0
            self._lower_last = None
            return value

        # A charger-internal data outage can publish zero for several cycles.
        # Count a lower sequence only when it is actually rising again, which
        # distinguishes a real reset followed by new consumption from a stuck
        # placeholder zero.
        if self._lower_last is None or value < self._lower_last:
            self._lower_count = 1
            self._lower_last = value
        elif value > self._lower_last:
            self._lower_count += 1
            self._lower_last = value
        if self._lower_count >= self.confirmations:
            self.accepted = value
            self._lower_count = 0
            self._lower_last = None
            return value
        return self.accepted


def _sensor(
    key: str,
    *,
    unit: str | None = None,
    device_class: str | None = None,
    state_class: str | None = None,
    icon: str | None = None,
    precision: int | None = None,
    enabled: bool = True,
    diagnostic: bool = False,
    options: tuple[str, ...] | None = None,
) -> VersiChargeSensorDescription:
    return VersiChargeSensorDescription(
        key=key,
        translation_key=f"versicharge_{key}",
        unit=unit,
        device_class=device_class,
        state_class=state_class,
        icon=icon,
        precision=precision,
        enabled_default=enabled,
        diagnostic=diagnostic,
        options=options,
    )


VERSICHARGE_SENSORS: Final = (
    # Native Energy Dashboard pair.
    _sensor(
        "energy_total",
        unit="kWh",
        device_class="energy",
        state_class="total_increasing",
        precision=3,
    ),
    _sensor(
        "active_power_total",
        unit="W",
        device_class="power",
        state_class="measurement",
        precision=0,
    ),
    # Charger state and actionable feedback.
    _sensor(
        "evse_state",
        device_class="enum",
        icon="mdi:ev-station",
        options=(
            "not_connected",
            "connected",
            "charging",
            "recoverable_fault",
            "non_recoverable_fault",
            "unknown",
        ),
    ),
    _sensor(
        "ocpp_state",
        device_class="enum",
        icon="mdi:cloud-sync-outline",
        options=tuple(OCPP_STATES.values()) + ("unknown",),
    ),
    _sensor(
        "error",
        device_class="enum",
        icon="mdi:alert-circle-outline",
        options=tuple(
            sorted(set(LEGACY_ERROR_CODES.values()) | set(MODERN_ERROR_CODES.values()))
        )
        + ("unknown",),
    ),
    _sensor(
        "charging_current_limit",
        unit="A",
        device_class="current",
        state_class="measurement",
        precision=0,
    ),
    _sensor(
        "minimum_charging_power",
        unit="W",
        device_class="power",
        state_class="measurement",
        precision=0,
        icon="mdi:arrow-collapse-down",
    ),
    _sensor(
        "maximum_charging_power",
        unit="W",
        device_class="power",
        state_class="measurement",
        precision=0,
        icon="mdi:arrow-collapse-up",
        enabled=False,
    ),
    _sensor(
        "charger_phase",
        device_class="enum",
        icon="mdi:sine-wave",
        options=("single_phase", "three_phase", "unknown"),
    ),
    _sensor(
        "effective_phase_count",
        icon="mdi:numeric",
        enabled=False,
        diagnostic=True,
    ),
    # Electrical measurements.
    *(
        _sensor(
            key,
            unit="A",
            device_class="current",
            state_class="measurement",
            precision=0,
        )
        for key in ("current_l1", "current_l2", "current_l3", "current_phase_sum")
    ),
    *(
        _sensor(
            key,
            unit="V",
            device_class="voltage",
            state_class="measurement",
            precision=0,
            enabled=key in {"voltage_l1_n", "voltage_l2_n", "voltage_l3_n"},
        )
        for key in (
            "voltage_l1_n",
            "voltage_l2_n",
            "voltage_l3_n",
            "voltage_l1_l2",
            "voltage_l2_l3",
            "voltage_l3_l1",
        )
    ),
    *(
        _sensor(
            key,
            unit="W",
            device_class="power",
            state_class="measurement",
            precision=0,
            enabled=False,
        )
        for key in ("active_power_l1", "active_power_l2", "active_power_l3")
    ),
    _sensor(
        "active_power_total_reported",
        unit="W",
        device_class="power",
        state_class="measurement",
        precision=0,
        enabled=False,
        diagnostic=True,
    ),
    *(
        _sensor(
            key,
            unit="VA",
            device_class="apparent_power",
            state_class="measurement",
            precision=0,
            enabled=False,
        )
        for key in (
            "apparent_power_l1",
            "apparent_power_l2",
            "apparent_power_l3",
            "apparent_power_total",
        )
    ),
    *(
        _sensor(
            key,
            unit="var",
            device_class="reactive_power",
            state_class="measurement",
            precision=0,
            enabled=False,
        )
        for key in (
            "reactive_power_l1",
            "reactive_power_l2",
            "reactive_power_l3",
            "reactive_power_total",
        )
    ),
    *(
        _sensor(
            key,
            device_class="power_factor",
            state_class="measurement",
            precision=3,
            enabled=False,
        )
        for key in (
            "power_factor_l1",
            "power_factor_l2",
            "power_factor_l3",
            "power_factor_average",
        )
    ),
    # Temperatures and charger-native fallback configuration.
    *(
        _sensor(
            key,
            unit="°C",
            device_class="temperature",
            state_class="measurement",
            precision=0,
            enabled=False,
            diagnostic=True,
        )
        for key in (
            "temperature_onboard_a",
            "temperature_onboard_b",
            "temperature_offboard_a",
            "temperature_offboard_b",
        )
    ),
    _sensor(
        "fallback_current",
        unit="A",
        device_class="current",
        enabled=False,
        diagnostic=True,
    ),
    _sensor(
        "fallback_time",
        unit="s",
        device_class="duration",
        enabled=False,
        diagnostic=True,
    ),
    _sensor(
        "session_energy_target_raw",
        icon="mdi:target",
        enabled=False,
        diagnostic=True,
    ),
    # Static configuration and identification diagnostics.
    _sensor("production_date", icon="mdi:calendar", enabled=False, diagnostic=True),
    _sensor(
        "platform_type",
        device_class="enum",
        icon="mdi:ev-station",
        enabled=False,
        diagnostic=True,
        options=tuple(PLATFORM_TYPES.values()) + ("unknown",),
    ),
    _sensor("number_of_outlets", icon="mdi:ev-plug-type2", enabled=False, diagnostic=True),
    _sensor(
        "outlet_type",
        device_class="enum",
        icon="mdi:ev-plug-type2",
        enabled=False,
        diagnostic=True,
        options=tuple(OUTLET_TYPES.values()) + ("unknown",),
    ),
    _sensor(
        "delay_setting",
        device_class="enum",
        icon="mdi:timer-outline",
        enabled=False,
        diagnostic=True,
        options=("off", "2_hours", "4_hours", "6_hours", "8_hours", "unknown"),
    ),
    _sensor(
        "connectivity",
        device_class="enum",
        icon="mdi:lan-connect",
        enabled=False,
        diagnostic=True,
        options=tuple(CONNECTIVITY_TYPES.values()) + ("unknown",),
    ),
    _sensor("rated_current", unit="A", device_class="current", enabled=False, diagnostic=True),
    _sensor("installation_current", unit="A", device_class="current", diagnostic=True),
    _sensor(
        "meter_type",
        device_class="enum",
        icon="mdi:meter-electric-outline",
        enabled=False,
        diagnostic=True,
        options=tuple(METER_TYPES.values()) + ("unknown",),
    ),
    _sensor("a8_firmware", icon="mdi:chip", diagnostic=True),
    _sensor("m0_firmware", icon="mdi:chip", enabled=False, diagnostic=True),
    _sensor("modbus_app_version", icon="mdi:counter", enabled=False, diagnostic=True),
    _sensor("firmware_variant", icon="mdi:identifier", enabled=False, diagnostic=True),
    _sensor("firmware_release_date", icon="mdi:calendar", enabled=False, diagnostic=True),
    _sensor(
        "register_profile",
        device_class="enum",
        icon="mdi:file-table-outline",
        diagnostic=True,
        options=("legacy", "modern", "modern_assumed"),
    ),
    _sensor("register_map", icon="mdi:file-table-outline", enabled=False, diagnostic=True),
    _sensor("modbus_unit_id", icon="mdi:numeric", diagnostic=True),
)

VERSICHARGE_STATIC_VALUE_KEYS: Final = tuple(
    sorted({
        definition.key for definition in STATIC_REGISTERS
    }
    | {
        "platform_type",
        "outlet_type",
        "delay_setting",
        "connectivity",
        "meter_type",
        "register_profile",
        "state_profile",
        "register_map",
        "modbus_unit_id",
    })
)
