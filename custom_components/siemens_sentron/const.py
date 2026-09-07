"""Constants for Siemens SENTRON."""

DOMAIN = "siemens_sentron"

DEFAULT_NAME = "SENTRON Powercenter"
DEFAULT_PORT = 502

DEFAULT_SCAN_START = 1
DEFAULT_SCAN_END = 24

GATEWAY_STARTUP_DELAY = 0
DISCOVERY_RETRIES = 1
DISCOVERY_RETRY_DELAY = 0
ECPD_STANDBY_COOLDOWN_SECONDS = 10
ECPD_UNLOCK_ACK_SECONDS = 90

GATEWAY_SLAVE = 255
GATEWAY_DISPLAY_ADDRESS = 0

PAC2200_SLAVE = 1
PAC2200_IM0_ADDRESS = 64001  # PAC2200 data dictionary: no -1 offset
PAC2200_IM0_COUNT = 27
PAC2200_PROFILE_ID = 0xF600
PAC2200_ORDER_PREFIX = "7KM2200"


# Gateway end-device status registers (Modbus offset -1 already applied).
GATEWAY_POC1000_PAIRING_STATUS_BASE = 1025
GATEWAY_POC1000_CONNECTION_STATE_BASE = 1050
GATEWAY_POC1100_BREAKER_STATE_BASE = 1200
GATEWAY_POC1100_CONNECTION_STATE_BASE = 16483

REGISTER_MANUFACTURER_ID = 1
REGISTER_GATEWAY_FIRMWARE = 21
REGISTER_ARTICLE_NUMBER = 2  # Modbus register 3, offset -1
REGISTER_ATTACHED_DEVICE_TYPE = 110
REGISTER_DEVICE_VARIANT = 111
REGISTER_DEVICE_FIRMWARE = 21

SIEMENS_MANUFACTURER_ID = 42
MANUFACTURER = "Siemens"

GATEWAY_DEVICE_KEY = "gateway"
SLAVES_KEY = "slaves"
VALUES_KEY = "values"

INVALID_VARIANTS = {0, 65535}

DEVICE_VARIANT_MAP = {
    0: {"device_type": "unknown", "model": "Unknown Device", "name_prefix": "Unknown"},
    1: {"device_type": "5ST3 COM AS+FC", "model": "5ST3 COM AS+FC", "name_prefix": "AS+FC"},
    2: {"device_type": "3NA3 COM Fuse", "model": "3NA3 COM Fuse", "name_prefix": "Fuse"},
    3: {"device_type": "5SL6 COM MCB", "model": "5SL6 COM MCB", "name_prefix": "MCB"},
    4: {"device_type": "5SV6 COM AFDD", "model": "5SV6 COM AFDD", "name_prefix": "AFDD"},
    5: {"device_type": "5ST3 COM RCA Standard", "model": "5ST3 COM RCA Standard", "name_prefix": "RCA"},
    6: {"device_type": "5ST3 COM RCA mit RCD/IR Test", "model": "5ST3 COM RCA mit RCD/IR Test", "name_prefix": "RCA Test"},
    7: {"device_type": "5SL6 COM MCB RCM", "model": "5SL6 COM MCB RCM", "name_prefix": "MCB RCM"},
    8: {"device_type": "5SV8 COM RCM", "model": "5SV8 COM RCM", "name_prefix": "RCM"},
    9: {"device_type": "3RV2 COM MSP", "model": "3RV2 COM MSP", "name_prefix": "MSP"},
    10: {"device_type": "5SV8 COM RCM", "model": "5SV8 COM RCM", "name_prefix": "RCM"},
    11: {"device_type": "5TY1 COM ECPD", "model": "5TY1 COM ECPD", "name_prefix": "ECPD"},
    12: {"device_type": "unknown", "model": "Unknown Device Variant 12", "name_prefix": "Unknown"},
    13: {"device_type": "unknown", "model": "Unknown Device Variant 13", "name_prefix": "Unknown"},
    14: {"device_type": "POC1100", "model": "SENTRON Powercenter 1100", "name_prefix": "POC1100"},
    15: {"device_type": "unknown", "model": "Unknown Device Variant 15", "name_prefix": "Unknown"},
    16: {"device_type": "POC2000", "model": "SENTRON Powercenter 2000", "name_prefix": "POC2000"},
    17: {"device_type": "unknown", "model": "Unknown Device Variant 17", "name_prefix": "Unknown"},
    18: {"device_type": "5TT4 COM DIDO", "model": "5TT4 COM DIDO", "name_prefix": "DIDO"},
    19: {"device_type": "3NA6 COM Fuse", "model": "3NA6 COM Fuse", "name_prefix": "Fuse"},
}


# Article/order number based fallback for slaves that report Device Variant = 0.
# Keys are prefixes/fragments normalized to uppercase. Values are DEVICE_VARIANT_MAP keys.
ARTICLE_NUMBER_VARIANT_HINTS = {
    "5ST3": 1,
    "3NA3": 2,
    "5SL6": 3,
    "5SV6": 4,
    "5ST30": 5,
    "5ST31": 6,
    "5SL60": 7,
    "5SV8": 8,
    "3RV2": 9,
    "5TY1": 11,
    "5TT4": 18,
    "3NA6": 19,
}

GATEWAY_VARIANT_MAP = {
    14: "SENTRON Powercenter 1100",
    16: "SENTRON Powercenter 2000",
}

ECPD_SWITCH_VARIANTS = {11}
ECPD_CONFIG_VARIANTS = {11}
RCA_SWITCH_VARIANTS = {5, 6}
RCA_CONFIG_VARIANTS = {1, 5, 6}
RCM_TEST_VARIANTS = {7}  # 5SL6 COM MCB RCM: RCM test button/result/timestamp enabled; combined Test Status RCM remains disabled
MCB_RCM_VARIANTS = {7}
GATEWAY_BREAKER_STATE_VARIANTS = {1, 3, 4, 7, 11}

# Availability from Modbus map (end-device columns only, Modbus offset -1 applied in addresses below).
ALARM_STATE_VARIANTS = {variant for variant in DEVICE_VARIANT_MAP if variant not in GATEWAY_VARIANT_MAP and variant != 0}
COMMON_ENDDEVICE_VARIANTS = {1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 18, 19}
COMMON_DIAGNOSTIC_VARIANTS = COMMON_ENDDEVICE_VARIANTS
COMMON_TEMPERATURE_VARIANTS = COMMON_ENDDEVICE_VARIANTS
COMMON_RSSI_VARIANTS = COMMON_ENDDEVICE_VARIANTS
LOCALIZE_SWITCH_VARIANTS = {1, 3, 4, 5, 6, 7, 8, 9, 10, 11, 18, 19}
COMMON_CURRENT_VARIANTS = {2, 3, 4, 7, 11, 19}
DIDO_VARIANTS = {18}

CONNECTION_STATE_PROFILE_ITEM = {"key": "connection_state", "name": "Verbindungsstatus", "kind": "gateway_connection_state", "enabled_default": True, "diagnostic": True}
GATEWAY_BREAKER_STATE_PROFILE_ITEM = {"key": "breaker_state", "name": "Schalterzustand", "kind": "gateway_breaker_state", "enabled_default": True, "source": "powercenter_dependent"}

BREAKER_STATE_MAP = {
    0: "Unknown",
    1: "Off",
    2: "On",
    3: "Tripped",
    4: "Tripped, but handle blocked",
    5: "Standby (ECPD)",
    6: "Standby tripped (ECPD)",
}

RCA_HANDLE_STATE_MAP = {
    0: "Unknown",
    1: "Off: manual",
    2: "On: manual",
    3: "Off: manual off reset failed",
    4: "On: remote",
    5: "Off: remote",
    6: "On: ARD",
    7: "Off: Trip",
}

RCA_HANDLE_ON_STATES = {2, 4, 6}
RCA_HANDLE_OFF_STATES = {1, 3, 5, 7}

CONNECTION_STATE_MAP = {
    0: "Idle",
    1: "Offline",
    2: "Connecting",
    3: "Connected",
}

DEVICE_STATE_MAP = {
    0: "Device ON",
    1: "Device ON, Error",
    2: "Device Standby",
    3: "Device Standby, Error",
    4: "Device OFF",
    5: "Device OFF, Error",
}

ALARM_STATE_MAP = {
    0: "No alarm",
    1: "Alarm",
}

ATTACHED_DEVICE_TYPE_OPTIONS = {
    0: "Unknown",
    1: "RCD",
    2: "MCB",
    3: "SCD",
    4: "AFDD",
    5: "RCBO",
}

ARD_AUTO_RECLOSE_OPTIONS = {
    0: "Disabled",
    1: "Enabled",
}

REMOTE_CONTROL_SELECTOR_OPTIONS = {
    0: "Wired signal",
    1: "Communication commands",
}

ECPD_NOMINAL_CURRENT_OPTIONS = {
    300: "0.3 A",
    500: "0.5 A",
    1000: "1 A",
    1600: "1.6 A",
    2000: "2 A",
    3000: "3 A",
    4000: "4 A",
    5000: "5 A",
    6000: "6 A",
    8000: "8 A",
    10000: "10 A",
    13000: "13 A",
    15000: "15 A",
    16000: "16 A",
}

ECPD_TRIP_BEHAVIOUR_OPTIONS = {
    1: "STANDBY",
    2: "STANDBY and reclose",
    3: "OFF",
}

ECPD_RCD_SENSITIVITY_OPTIONS = {
    1: "NORMAL",
    2: "SENSITIVE",
    3: "ROBUST",
}

ECPD_RCD_TRIPPING_TIME_OPTIONS = {
    1: "NORMAL",
    2: "FAST",
}

DEVICE_PROFILES = {
    "5ST3 COM AS+FC": [
        {"key": "breaker_state", "name": "Schalterzustand", "kind": "gateway_breaker_state", "enabled_default": True, "source": "powercenter_dependent"},
        {"key": "connection_state", "name": "Verbindungsstatus", "kind": "gateway_connection_state", "enabled_default": True, "diagnostic": True},
        {"key": "firmware", "name": "Firmware", "kind": "holding_firmware", "address": 21, "count": 2, "enabled_default": True, "diagnostic": True},
    ],
    "5ST3 COM RCA Standard": [
        {"key": "rca_handle_state", "name": "Handle State", "kind": "input_u16", "address": 3111, "enabled_default": True},
        {"key": "connection_state", "name": "Verbindungsstatus", "kind": "gateway_connection_state", "enabled_default": True, "diagnostic": True},
        {"key": "firmware", "name": "Firmware", "kind": "holding_firmware", "address": 21, "count": 2, "enabled_default": True, "diagnostic": True},
    ],
    "5ST3 COM RCA mit RCD/IR Test": [
        {"key": "rca_handle_state", "name": "Handle State", "kind": "input_u16", "address": 3111, "enabled_default": True},
        {"key": "connection_state", "name": "Verbindungsstatus", "kind": "gateway_connection_state", "enabled_default": True, "diagnostic": True},
        {"key": "firmware", "name": "Firmware", "kind": "holding_firmware", "address": 21, "count": 2, "enabled_default": True, "diagnostic": True},
    ],
    "5SL6 COM MCB": [
        {"key": "active_power", "name": "Leistung Wirkleistung", "kind": "input_float32", "address": 3085, "unit": "W", "device_class": "power", "state_class": "measurement", "enabled_default": True},
        {"key": "apparent_power", "name": "Leistung Scheinleistung", "kind": "input_float32", "address": 3087, "unit": "VA", "device_class": "apparent_power", "state_class": "measurement", "enabled_default": False},
        {"key": "energy_import", "name": "Energie Import", "kind": "input_float64", "address": 3093, "unit": "kWh", "scale": 0.001, "device_class": "energy", "state_class": "total_increasing", "enabled_default": True},
        {"key": "energy_export", "name": "Energie Export", "kind": "input_float64", "address": 3097, "unit": "kWh", "scale": 0.001, "device_class": "energy", "state_class": "total_increasing", "enabled_default": True},
        {"key": "current", "name": "Strom", "kind": "input_float32", "address": 3075, "unit": "A", "device_class": "current", "state_class": "measurement", "enabled_default": True},
        {"key": "breaker_state", "name": "Schalterzustand", "kind": "gateway_breaker_state", "enabled_default": True},
        {"key": "temperature", "name": "Temperatur", "kind": "input_float32", "address": 3071, "unit": "°C", "device_class": "temperature", "state_class": "measurement", "enabled_default": True},
        {"key": "power_factor", "name": "Leistung Leistungsfaktor", "kind": "input_float32", "address": 3091, "enabled_default": True},
        {"key": "reactive_power", "name": "Leistung Blindleistung", "kind": "input_float32", "address": 3089, "unit": "var", "state_class": "measurement", "enabled_default": True},
        {"key": "voltage", "name": "Spannung", "kind": "input_float32", "address": 3081, "unit": "V", "device_class": "voltage", "state_class": "measurement", "enabled_default": True},
        {"key": "frequency", "name": "Frequenz", "kind": "input_float32", "address": 3083, "unit": "Hz", "state_class": "measurement", "enabled_default": True},
        {"key": "firmware", "name": "Firmware", "kind": "holding_firmware", "address": 21, "count": 2, "enabled_default": True, "diagnostic": True},
    ],
    "5SL6 COM MCB RCM": [
        {"key": "active_power", "name": "Leistung Wirkleistung", "kind": "input_float32", "address": 3085, "unit": "W", "device_class": "power", "state_class": "measurement", "enabled_default": True},
        {"key": "apparent_power", "name": "Leistung Scheinleistung", "kind": "input_float32", "address": 3087, "unit": "VA", "device_class": "apparent_power", "state_class": "measurement", "enabled_default": False},
        {"key": "energy_import", "name": "Energie Import", "kind": "input_float64", "address": 3093, "unit": "kWh", "scale": 0.001, "device_class": "energy", "state_class": "total_increasing", "enabled_default": True},
        {"key": "energy_export", "name": "Energie Export", "kind": "input_float64", "address": 3097, "unit": "kWh", "scale": 0.001, "device_class": "energy", "state_class": "total_increasing", "enabled_default": True},
        {"key": "current", "name": "Strom", "kind": "input_float32", "address": 3075, "unit": "A", "device_class": "current", "state_class": "measurement", "enabled_default": True},
        {"key": "breaker_state", "name": "Schalterzustand", "kind": "gateway_breaker_state", "enabled_default": True},
        {"key": "rcm_test_status", "name": "Test letztes Ergebnis (RCM)", "kind": "input_u16", "address": 2651, "enabled_default": True, "diagnostic": True},
        {"key": "rcm_test_timestamp", "name": "Test letzter Zeitstempel (RCM)", "kind": "input_unix_time", "address": 3137, "enabled_default": True, "diagnostic": True},
        {"key": "rcm_rms_low_pass", "name": "RCM RMS Messwert", "kind": "input_float32", "address": 3335, "unit": "mA", "scale": 1000, "state_class": "measurement", "enabled_default": True},
        {"key": "leakage", "name": "Fehlerstrom", "kind": "input_float32", "address": 3335, "unit": "mA", "scale": 1000, "state_class": "measurement", "enabled_default": False},
        {"key": "temperature", "name": "Temperatur", "kind": "input_float32", "address": 3071, "unit": "°C", "device_class": "temperature", "state_class": "measurement", "enabled_default": True},
        {"key": "power_factor", "name": "Leistung Leistungsfaktor", "kind": "input_float32", "address": 3091, "enabled_default": True},
        {"key": "reactive_power", "name": "Leistung Blindleistung", "kind": "input_float32", "address": 3089, "unit": "var", "state_class": "measurement", "enabled_default": True},
        {"key": "voltage", "name": "Spannung", "kind": "input_float32", "address": 3081, "unit": "V", "device_class": "voltage", "state_class": "measurement", "enabled_default": True},
        {"key": "frequency", "name": "Frequenz", "kind": "input_float32", "address": 3083, "unit": "Hz", "state_class": "measurement", "enabled_default": True},
        {"key": "firmware", "name": "Firmware", "kind": "holding_firmware", "address": 21, "count": 2, "enabled_default": True, "diagnostic": True},
    ],
    "5SV8 COM RCM": [
        {"key": "leakage", "name": "Fehlerstrom", "kind": "input_float32", "address": 3341, "unit": "mA", "scale": 1000, "state_class": "measurement", "enabled_default": True},
        {"key": "temperature", "name": "Temperatur", "kind": "input_float32", "address": 3071, "unit": "°C", "device_class": "temperature", "state_class": "measurement", "enabled_default": True},
        {"key": "firmware", "name": "Firmware", "kind": "holding_firmware", "address": 21, "count": 2, "enabled_default": True, "diagnostic": True},
    ],
    "5SV6 COM AFDD": [
        {"key": "active_power", "name": "Leistung Wirkleistung", "kind": "input_float32", "address": 3085, "unit": "W", "device_class": "power", "state_class": "measurement", "enabled_default": True},
        {"key": "apparent_power", "name": "Leistung Scheinleistung", "kind": "input_float32", "address": 3087, "unit": "VA", "device_class": "apparent_power", "state_class": "measurement", "enabled_default": False},
        {"key": "energy_import", "name": "Energie Import", "kind": "input_float64", "address": 3093, "unit": "kWh", "scale": 0.001, "device_class": "energy", "state_class": "total_increasing", "enabled_default": True},
        {"key": "energy_export", "name": "Energie Export", "kind": "input_float64", "address": 3097, "unit": "kWh", "scale": 0.001, "device_class": "energy", "state_class": "total_increasing", "enabled_default": True},
        {"key": "current", "name": "Strom", "kind": "input_float32", "address": 3075, "unit": "A", "device_class": "current", "state_class": "measurement", "enabled_default": True},
        {"key": "breaker_state", "name": "Schalterzustand", "kind": "gateway_breaker_state", "enabled_default": True},
        {"key": "alarm_state", "name": "Alarmzustand", "kind": "input_u16", "address": 3109, "enabled_default": True},
        {"key": "temperature", "name": "Temperatur", "kind": "input_float32", "address": 3071, "unit": "°C", "device_class": "temperature", "state_class": "measurement", "enabled_default": True},
        {"key": "power_factor", "name": "Leistung Leistungsfaktor", "kind": "input_float32", "address": 3091, "enabled_default": True},
        {"key": "reactive_power", "name": "Leistung Blindleistung", "kind": "input_float32", "address": 3089, "unit": "var", "state_class": "measurement", "enabled_default": True},
        {"key": "voltage", "name": "Spannung", "kind": "input_float32", "address": 3081, "unit": "V", "device_class": "voltage", "state_class": "measurement", "enabled_default": True},
        {"key": "frequency", "name": "Frequenz", "kind": "input_float32", "address": 3083, "unit": "Hz", "state_class": "measurement", "enabled_default": True},
        {"key": "firmware", "name": "Firmware", "kind": "holding_firmware", "address": 21, "count": 2, "enabled_default": True, "diagnostic": True},
    ],
    "5TY1 COM ECPD": [
        # Diagnosis (Modbus map register - 1)
        {"key": "alarm_state", "name": "Alarmzustand", "kind": "input_u32", "address": 2559, "enabled_default": True, "diagnostic": True},
        {"key": "last_state_rcd_test", "name": "Letzter RCD-Test", "kind": "input_u16", "address": 2634, "enabled_default": True, "diagnostic": True},
        {"key": "device_test_status", "name": "Gerätetest Status", "kind": "input_u16", "address": 2678, "enabled_default": True, "diagnostic": True},
        # Native ECPD timestamp; kept for the combined Self-RCD test status sensor.
        {"key": "device_test_timestamp", "name": "Test letzter Zeitstempel (Self-RCD)", "kind": "input_unix_time", "address": 3137, "enabled_default": True, "diagnostic": True},
        {"key": "unlock_status", "name": "Unlock Status", "kind": "input_u16", "address": 3113, "enabled_default": True, "diagnostic": True},

        # Metering (Modbus map register - 1)
        {"key": "temperature", "name": "Temperatur", "kind": "input_float32", "address": 3071, "unit": "°C", "device_class": "temperature", "state_class": "measurement", "enabled_default": True},
        {"key": "current", "name": "Strom", "kind": "input_float32", "address": 3075, "unit": "A", "device_class": "current", "state_class": "measurement", "enabled_default": True},
        {"key": "voltage", "name": "Spannung", "kind": "input_float32", "address": 3081, "unit": "V", "device_class": "voltage", "state_class": "measurement", "enabled_default": True},
        {"key": "frequency", "name": "Frequenz", "kind": "input_float32", "address": 3083, "unit": "Hz", "state_class": "measurement", "enabled_default": True},
        {"key": "active_power", "name": "Leistung Wirkleistung", "kind": "input_float32", "address": 3085, "unit": "W", "device_class": "power", "state_class": "measurement", "enabled_default": True},
        {"key": "apparent_power", "name": "Leistung Scheinleistung", "kind": "input_float32", "address": 3087, "unit": "VA", "device_class": "apparent_power", "state_class": "measurement", "enabled_default": True},
        {"key": "reactive_power", "name": "Leistung Blindleistung", "kind": "input_float32", "address": 3089, "unit": "var", "state_class": "measurement", "enabled_default": True},
        {"key": "power_factor", "name": "Leistung Leistungsfaktor", "kind": "input_float32", "address": 3091, "state_class": "measurement", "enabled_default": True},
        {"key": "breaker_state", "name": "Schalterzustand", "kind": "gateway_breaker_state", "enabled_default": True},
        {"key": "connection_state", "name": "Verbindungsstatus", "kind": "gateway_connection_state", "enabled_default": True, "diagnostic": True},
        {"key": "rcm_ac_low_pass", "name": "RCM AC Low Pass", "kind": "input_float32", "address": 3329, "unit": "mA", "scale": 1000, "state_class": "measurement", "enabled_default": True},
        {"key": "rcm_ac_basic_frequency", "name": "RCM AC Grundfrequenz", "kind": "input_float32", "address": 3337, "unit": "mA", "scale": 1000, "state_class": "measurement", "enabled_default": True},

        {"key": "alarm_trip_active", "name": "Trip aktiv", "kind": "gateway_breaker_state_match", "matches": [3], "enabled_default": True},
        {"key": "alarm_rcm_active", "name": "RCM-Alarm aktiv", "kind": "input_u32_mask", "address": 2559, "mask": 1 << 25, "enabled_default": True},
        {"key": "firmware", "name": "Firmware", "kind": "holding_firmware", "address": 21, "count": 2, "enabled_default": True, "diagnostic": True},
    ],
}



# Product/help links shown in the Home Assistant device card.
# Gateways and standalone PAC2200 devices use their local web interface when available.
DEFAULT_DEVICE_CONFIGURATION_URL = "https://www.siemens.com/en-us/products/sentron/"
POWER_CENTER_CONFIGURATION_URL = "https://www.siemens.com/en-us/products/sentron/capable-circuit-protection-devices/"
DEVICE_CONFIGURATION_URL_BY_TYPE = {
    # Specific device/product families
    "PAC2200": "https://www.siemens.com/en-us/products/sentron/measuring-devices/",
    "PAC 2200": "https://www.siemens.com/en-us/products/sentron/measuring-devices/",
    "5TY1 COM ECPD": "https://www.siemens.com/en-us/products/sentron/sentron-ecpd/",
    "ECPD": "https://www.siemens.com/en-us/products/sentron/sentron-ecpd/",
    "5SV6 COM AFDD": "https://www.siemens.com/en-us/products/sentron/arc-fault-detection-devices/",
    "AFDD": "https://www.siemens.com/en-us/products/sentron/arc-fault-detection-devices/",
    "5SL6 COM MCB RCM": "https://www.siemens.com/en-us/products/sentron/miniature-circuit-breakers/",
    "5SL6 COM MCB": "https://www.siemens.com/en-us/products/sentron/miniature-circuit-breakers/",
    "MCB RCM": "https://www.siemens.com/en-us/products/sentron/miniature-circuit-breakers/",
    "MCB": "https://www.siemens.com/en-us/products/sentron/miniature-circuit-breakers/",
    "Leitungsschutzschalter": "https://www.siemens.com/en-us/products/sentron/miniature-circuit-breakers/",

    # Powercenter gateways and remaining Powercenter slave devices
    "POC1000": POWER_CENTER_CONFIGURATION_URL,
    "Powercenter 1000": POWER_CENTER_CONFIGURATION_URL,
    "POC1100": POWER_CENTER_CONFIGURATION_URL,
    "Powercenter 1100": POWER_CENTER_CONFIGURATION_URL,
    "POC2000": POWER_CENTER_CONFIGURATION_URL,
    "Powercenter 2000": POWER_CENTER_CONFIGURATION_URL,
    "5SV8 COM RCM": POWER_CENTER_CONFIGURATION_URL,
    "5ST3 COM RCA Standard": POWER_CENTER_CONFIGURATION_URL,
    "5ST3 COM RCA mit RCD/IR Test": POWER_CENTER_CONFIGURATION_URL,
    "5ST3 COM AS+FC": POWER_CENTER_CONFIGURATION_URL,
    "3NA3 COM Fuse": POWER_CENTER_CONFIGURATION_URL,
    "3NA6 COM Fuse": POWER_CENTER_CONFIGURATION_URL,
    "3RV2 COM MSP": POWER_CENTER_CONFIGURATION_URL,
    "5TT4 COM DIDO": POWER_CENTER_CONFIGURATION_URL,
}


def get_device_configuration_url(info: dict | None = None, *, gateway: dict | None = None, prefer_local: bool = False) -> str:
    """Return the best URL for the Home Assistant device card."""
    if (gateway or info or {}).get("device_kind") == "versicharge":
        # VersiCharge is commissioned through Sifinity Go rather than a local
        # HTTP UI, so linking to the host would normally lead to a dead page.
        return "https://www.siemens.com/versicharge"
    if prefer_local and gateway and gateway.get("host"):
        return f"http://{gateway['host']}"
    info = info or {}
    for key in (
        str(info.get("model", "")),
        str(info.get("device_type", "")),
        str(info.get("type_label", "")),
        str(info.get("name", "")),
    ):
        for needle, url in DEVICE_CONFIGURATION_URL_BY_TYPE.items():
            if needle and needle.lower() in key.lower():
                return url
    return DEFAULT_DEVICE_CONFIGURATION_URL
