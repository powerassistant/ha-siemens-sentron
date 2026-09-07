"""Device profile registry for Siemens SENTRON entities.

This module is intentionally the only place where end-device entity datasets
are composed. Root devices (Powercenter gateways / PAC2200) are handled in
separate onboarding and gateway-sensor paths to avoid side effects.
"""

from __future__ import annotations

from .const import (
    ALARM_STATE_VARIANTS,
    COMMON_CURRENT_VARIANTS,
    COMMON_DIAGNOSTIC_VARIANTS,
    COMMON_RSSI_VARIANTS,
    COMMON_TEMPERATURE_VARIANTS,
    CONNECTION_STATE_PROFILE_ITEM,
    DEVICE_PROFILES,
    DIDO_VARIANTS,
    GATEWAY_BREAKER_STATE_PROFILE_ITEM,
    GATEWAY_BREAKER_STATE_VARIANTS,
)


def get_effective_device_profile(slave_info: dict) -> list[dict]:
    """Return profile plus map-driven gateway/common sensors per end device."""
    profile = list(DEVICE_PROFILES.get(slave_info.get("device_type"), []))
    variant = slave_info.get("variant")

    # Connection State is a gateway RF/end-device status and is shown for every discovered slave.
    if not any(item.get("key") == "connection_state" for item in profile):
        profile.append(CONNECTION_STATE_PROFILE_ITEM)

    # Breaker State is sourced from the gateway for supported switching devices.
    if variant in GATEWAY_BREAKER_STATE_VARIANTS:
        profile = [item for item in profile if not (item.get("key") == "breaker_state" and item.get("kind") != "gateway_breaker_state")]
        if not any(item.get("key") == "breaker_state" for item in profile):
            profile.append(GATEWAY_BREAKER_STATE_PROFILE_ITEM)

    # Alarm State is present for all end-device variants in the Modbus map.
    # Register 2560, Modbus offset -1 => address 2559. It is an operational
    # protection state and therefore a primary sensor, not diagnostics.
    if variant in ALARM_STATE_VARIANTS:
        profile = [item for item in profile if item.get("key") != "alarm_state"]
        profile.append({"key": "alarm_state", "name": "Alarmzustand", "kind": "input_u32", "address": 2559, "enabled_default": True})

    # Standard operating-hours diagnosis from Modbus map: Register 2578, offset -1.
    if variant in COMMON_DIAGNOSTIC_VARIANTS:
        profile = [item for item in profile if item.get("key") != "operating_hours_overall"]
        profile.append({"key": "operating_hours_overall", "name": "Betriebsstunden Gesamt", "kind": "input_float64", "address": 2577, "unit": "h", "scale": 1 / 3600, "state_class": "total_increasing", "enabled_default": True, "diagnostic": True})

    # Radio signal strength RSSI from Modbus map: Register 2622, offset -1.
    if variant in COMMON_RSSI_VARIANTS:
        profile = [item for item in profile if item.get("key") != "radio_signal_strength_rssi"]
        profile.append({"key": "radio_signal_strength_rssi", "name": "Funksignal RSSI", "kind": "input_i16", "address": 2621, "unit": "dBm", "state_class": "measurement", "enabled_default": True, "diagnostic": True})

    # Standard temperatures from Modbus map: Register 3072 / 3074, offset -1.
    if variant in COMMON_TEMPERATURE_VARIANTS:
        if not any(item.get("key") == "temperature" for item in profile):
            profile.append({"key": "temperature", "name": "Temperatur", "kind": "input_float32", "address": 3071, "unit": "°C", "device_class": "temperature", "state_class": "measurement", "enabled_default": True})
        if not any(item.get("key") == "average_temperature" for item in profile):
            profile.append({"key": "average_temperature", "name": "Temperatur Durchschnitt", "kind": "input_float32", "address": 3073, "unit": "°C", "device_class": "temperature", "state_class": "measurement", "enabled_default": True})

    # Standard current from Modbus map: Register 3076, offset -1.
    # This keeps 3NA3 COM Fuse consistent with other devices that expose the same data point.
    if variant in COMMON_CURRENT_VARIANTS:
        if not any(item.get("key") == "current" for item in profile):
            profile.append({"key": "current", "name": "Strom", "kind": "input_float32", "address": 3075, "unit": "A", "device_class": "current", "state_class": "measurement", "enabled_default": True})

    # DIDO only: input bits and output forcing states from Modbus map.
    # Plain output-state entities are intentionally not created because they are redundant
    # to the output control switches.
    if variant in DIDO_VARIANTS:
        profile = [item for item in profile if item.get("key") not in {"dido_input_1", "dido_input_2", "output_1_state", "output_2_state", "output_1_forcing", "output_2_forcing"}]
        profile.extend([
            {"key": "dido_input_1", "name": "Eingang 1", "kind": "input_u16_mask", "address": 3114, "mask": 1, "enabled_default": True},
            {"key": "dido_input_2", "name": "Eingang 2", "kind": "input_u16_mask", "address": 3114, "mask": 2, "enabled_default": True},
            {"key": "output_1_forcing", "name": "Ausgang 1 Forcing", "kind": "input_output_forcing", "address": 3139, "enabled_default": True, "diagnostic": True},
            {"key": "output_2_forcing", "name": "Ausgang 2 Forcing", "kind": "input_output_forcing", "address": 3141, "enabled_default": True, "diagnostic": True},
        ])

    return profile
