"""Standalone PAC2200 data model for Siemens SENTRON."""

from __future__ import annotations

from dataclasses import dataclass
from homeassistant.const import EntityCategory

PAC2200_SLAVE_ID = 1


@dataclass(frozen=True)
class Pac2200SensorDescription:
    """Description of one PAC2200 Modbus sensor."""

    key: str
    name: str
    kind: str
    address: int
    unit: str | None = None
    device_class: str | None = None
    state_class: str | None = None
    icon: str | None = None
    entity_category: EntityCategory | None = None
    scale: float | None = None
    precision: int | None = None
    enabled_default: bool = True


VOLTAGE = "voltage"
CURRENT = "current"
POWER = "power"
REACTIVE_POWER = "reactive_power"
APPARENT_POWER = "apparent_power"
ENERGY = "energy"
FREQUENCY = "frequency"
POWER_FACTOR = "power_factor"

MEASUREMENT = "measurement"
TOTAL_INCREASING = "total_increasing"


def _f32(key: str, name: str, address: int, unit: str | None, device_class: str | None,
         state_class: str | None = MEASUREMENT, icon: str | None = None,
         precision: int | None = None, enabled_default: bool = True) -> Pac2200SensorDescription:
    return Pac2200SensorDescription(
        key=key,
        name=name,
        kind="input_float32",
        address=address,
        unit=unit,
        device_class=device_class,
        state_class=state_class,
        icon=icon,
        precision=precision,
        enabled_default=enabled_default,
    )


def _u32(key: str, name: str, address: int, icon: str | None = None,
         entity_category: EntityCategory | None = None) -> Pac2200SensorDescription:
    return Pac2200SensorDescription(
        key=key,
        name=name,
        kind="input_u32",
        address=address,
        icon=icon,
        entity_category=entity_category,
    )


def _dt(key: str, name: str, address: int, enabled_default: bool = True) -> Pac2200SensorDescription:
    return Pac2200SensorDescription(
        key=key,
        name=name,
        kind="input_unix_time",
        address=address,
        icon="mdi:clock-outline",
        entity_category=EntityCategory.DIAGNOSTIC,
        enabled_default=enabled_default,
    )


def _energy(key: str, name: str, address: int, unit: str, enabled_default: bool = True) -> Pac2200SensorDescription:
    # PAC2200 exposes energy doubles in Wh / varh / VAh. Home Assistant gets kWh / kvarh / kVAh.
    # Home Assistant's energy device class only accepts active-energy units;
    # reactive/apparent energy remain total-increasing sensors without that class.
    return Pac2200SensorDescription(
        key=key,
        name=name,
        kind="input_float64",
        address=address,
        unit=unit,
        device_class=ENERGY if unit == "kWh" else None,
        state_class=TOTAL_INCREASING,
        icon="mdi:counter",
        scale=0.001,
        precision=3,
        enabled_default=enabled_default,
    )


PAC2200_SENSORS: tuple[Pac2200SensorDescription, ...] = (
    # Current
    _f32("current_average", "Current Phase Average", 61, "A", CURRENT, precision=2),
    _f32("current_l1", "Current L1", 13, "A", CURRENT, precision=2),
    _f32("current_l2", "Current L2", 15, "A", CURRENT, precision=2),
    _f32("current_l3", "Current L3", 17, "A", CURRENT, precision=2),
    _f32("current_neutral", "Neutral Current", 71, "A", CURRENT, precision=2),

    # Diagnostics / status
    _u32("device_diagnostics_status", "Device Diagnostics and Status", 205, "mdi:chip", EntityCategory.DIAGNOSTIC),
    _dt("date_time", "Date Time", 799, enabled_default=False),
    _u32("actual_tariff", "Actual Tariff", 211, "mdi:cash-multiple", EntityCategory.DIAGNOSTIC),
    _u32("state_binary_inputs", "Digital Input 1", 209, "mdi:electric-switch"),
    _u32("state_binary_outputs", "Digital Output 1", 207, "mdi:electric-switch"),
    _u32("counter_configurable", "Counter Configurable", 215, "mdi:counter"),

    # Energy - collective
    _energy("energy_active_import_tariff_1_collective", "Energy Active Import Tariff 1 Collective", 801, "kWh"),
    _energy("energy_active_import_tariff_2_collective", "Energy Active Import Tariff 2 Collective", 805, "kWh"),
    _energy("energy_active_export_tariff_1_collective", "Energy Active Export Tariff 1 Collective", 809, "kWh"),
    _energy("energy_active_export_tariff_2_collective", "Energy Active Export Tariff 2 Collective", 813, "kWh"),
    _energy("energy_reactive_import_tariff_1_collective", "Energy Reactive Import Tariff 1 Collective", 817, "kvarh", enabled_default=False),
    _energy("energy_reactive_import_tariff_2_collective", "Energy Reactive Import Tariff 2 Collective", 821, "kvarh", enabled_default=False),
    _energy("energy_reactive_export_tariff_1_collective", "Energy Reactive Export Tariff 1 Collective", 825, "kvarh", enabled_default=False),
    _energy("energy_reactive_export_tariff_2_collective", "Energy Reactive Export Tariff 2 Collective", 829, "kvarh", enabled_default=False),
    _energy("energy_apparent_tariff_1_collective", "Energy Apparent Tariff 1 Collective", 833, "kVAh", enabled_default=False),
    _energy("energy_apparent_tariff_2_collective", "Energy Apparent Tariff 2 Collective", 837, "kVAh", enabled_default=False),

    # Energy - L1
    _energy("energy_active_import_tariff_1_l1", "Energy Active Import Tariff 1 L1", 841, "kWh", enabled_default=False),
    _energy("energy_active_import_tariff_2_l1", "Energy Active Import Tariff 2 L1", 845, "kWh", enabled_default=False),
    _energy("energy_active_export_tariff_1_l1", "Energy Active Export Tariff 1 L1", 849, "kWh", enabled_default=False),
    _energy("energy_active_export_tariff_2_l1", "Energy Active Export Tariff 2 L1", 853, "kWh", enabled_default=False),
    _energy("energy_reactive_import_tariff_1_l1", "Energy Reactive Import Tariff 1 L1", 857, "kvarh", enabled_default=False),
    _energy("energy_reactive_import_tariff_2_l1", "Energy Reactive Import Tariff 2 L1", 861, "kvarh", enabled_default=False),
    _energy("energy_reactive_export_tariff_1_l1", "Energy Reactive Export Tariff 1 L1", 865, "kvarh", enabled_default=False),
    _energy("energy_reactive_export_tariff_2_l1", "Energy Reactive Export Tariff 2 L1", 869, "kvarh", enabled_default=False),
    _energy("energy_apparent_tariff_1_l1", "Energy Apparent Tariff 1 L1", 873, "kVAh", enabled_default=False),
    _energy("energy_apparent_tariff_2_l1", "Energy Apparent Tariff 2 L1", 877, "kVAh", enabled_default=False),

    # Energy - L2
    _energy("energy_active_import_tariff_1_l2", "Energy Active Import Tariff 1 L2", 881, "kWh", enabled_default=False),
    _energy("energy_active_import_tariff_2_l2", "Energy Active Import Tariff 2 L2", 885, "kWh", enabled_default=False),
    _energy("energy_active_export_tariff_1_l2", "Energy Active Export Tariff 1 L2", 889, "kWh", enabled_default=False),
    _energy("energy_active_export_tariff_2_l2", "Energy Active Export Tariff 2 L2", 893, "kWh", enabled_default=False),
    _energy("energy_reactive_import_tariff_1_l2", "Energy Reactive Import Tariff 1 L2", 897, "kvarh", enabled_default=False),
    _energy("energy_reactive_import_tariff_2_l2", "Energy Reactive Import Tariff 2 L2", 901, "kvarh", enabled_default=False),
    _energy("energy_reactive_export_tariff_1_l2", "Energy Reactive Export Tariff 1 L2", 905, "kvarh", enabled_default=False),
    _energy("energy_reactive_export_tariff_2_l2", "Energy Reactive Export Tariff 2 L2", 909, "kvarh", enabled_default=False),
    _energy("energy_apparent_tariff_1_l2", "Energy Apparent Tariff 1 L2", 913, "kVAh", enabled_default=False),
    _energy("energy_apparent_tariff_2_l2", "Energy Apparent Tariff 2 L2", 917, "kVAh", enabled_default=False),

    # Energy - L3
    _energy("energy_active_import_tariff_1_l3", "Energy Active Import Tariff 1 L3", 921, "kWh", enabled_default=False),
    _energy("energy_active_import_tariff_2_l3", "Energy Active Import Tariff 2 L3", 925, "kWh", enabled_default=False),
    _energy("energy_active_export_tariff_1_l3", "Energy Active Export Tariff 1 L3", 929, "kWh", enabled_default=False),
    _energy("energy_active_export_tariff_2_l3", "Energy Active Export Tariff 2 L3", 933, "kWh", enabled_default=False),
    _energy("energy_reactive_import_tariff_1_l3", "Energy Reactive Import Tariff 1 L3", 937, "kvarh", enabled_default=False),
    _energy("energy_reactive_import_tariff_2_l3", "Energy Reactive Import Tariff 2 L3", 941, "kvarh", enabled_default=False),
    _energy("energy_reactive_export_tariff_1_l3", "Energy Reactive Export Tariff 1 L3", 945, "kvarh", enabled_default=False),
    _energy("energy_reactive_export_tariff_2_l3", "Energy Reactive Export Tariff 2 L3", 949, "kvarh", enabled_default=False),
    _energy("energy_apparent_tariff_1_l3", "Energy Apparent Tariff 1 L3", 953, "kVAh", enabled_default=False),
    _energy("energy_apparent_tariff_2_l3", "Energy Apparent Tariff 2 L3", 957, "kVAh", enabled_default=False),

    # Frequency
    _f32("frequency", "Frequency", 55, "Hz", FREQUENCY, precision=2),

    # Power - apparent
    _f32("power_apparent_collective", "Power Apparent Collective", 63, "VA", APPARENT_POWER, icon="mdi:flash-triangle", precision=0, enabled_default=False),
    _f32("power_apparent_l1", "Power Apparent L1", 19, "VA", APPARENT_POWER, icon="mdi:flash-triangle", precision=0, enabled_default=False),
    _f32("power_apparent_l2", "Power Apparent L2", 21, "VA", APPARENT_POWER, icon="mdi:flash-triangle", precision=0, enabled_default=False),
    _f32("power_apparent_l3", "Power Apparent L3", 23, "VA", APPARENT_POWER, icon="mdi:flash-triangle", precision=0, enabled_default=False),

    # Power - active
    _f32("power_active_collective", "Power Active Collective", 65, "W", POWER, icon="mdi:flash", precision=0),
    _f32("power_active_l1", "Power Active L1", 25, "W", POWER, icon="mdi:flash", precision=0),
    _f32("power_active_l2", "Power Active L2", 27, "W", POWER, icon="mdi:flash", precision=0),
    _f32("power_active_l3", "Power Active L3", 29, "W", POWER, icon="mdi:flash", precision=0),
    _f32("power_active_max_actual_period", "Power Active Max Actual Period", 509, "W", POWER, icon="mdi:flash", precision=0),
    _f32("power_active_min_actual_period", "Power Active Min Actual Period", 511, "W", POWER, icon="mdi:flash", precision=0),

    # Power - reactive Q1
    _f32("power_reactive_q1_collective", "Power Reactive Q1 Collective", 67, "var", REACTIVE_POWER, icon="mdi:flash-outline", precision=0, enabled_default=False),
    _f32("power_reactive_q1_l1", "Power Reactive Q1 L1", 31, "var", REACTIVE_POWER, icon="mdi:flash-outline", precision=0, enabled_default=False),
    _f32("power_reactive_q1_l2", "Power Reactive Q1 L2", 33, "var", REACTIVE_POWER, icon="mdi:flash-outline", precision=0, enabled_default=False),
    _f32("power_reactive_q1_l3", "Power Reactive Q1 L3", 35, "var", REACTIVE_POWER, icon="mdi:flash-outline", precision=0, enabled_default=False),
    _f32("power_reactive_q1_max_actual_period", "Power Reactive Q1 Max Actual Period", 513, "var", REACTIVE_POWER, icon="mdi:flash-outline", precision=0, enabled_default=False),
    _f32("power_reactive_q1_min_actual_period", "Power Reactive Q1 Min Actual Period", 515, "var", REACTIVE_POWER, icon="mdi:flash-outline", precision=0, enabled_default=False),

    # Power factor
    _f32("power_factor_collective", "Power Factor Collective", 69, None, POWER_FACTOR, icon="mdi:angle-acute", precision=3, enabled_default=False),
    _f32("power_factor_l1", "Power Factor L1", 37, None, POWER_FACTOR, icon="mdi:angle-acute", precision=3, enabled_default=False),
    _f32("power_factor_l2", "Power Factor L2", 39, None, POWER_FACTOR, icon="mdi:angle-acute", precision=3, enabled_default=False),
    _f32("power_factor_l3", "Power Factor L3", 41, None, POWER_FACTOR, icon="mdi:angle-acute", precision=3, enabled_default=False),

    # Voltage
    _f32("voltage_average_ph_n", "Voltage L-N Average", 57, "V", VOLTAGE, precision=1),
    _f32("voltage_average_ph_ph", "Voltage L-L Average", 59, "V", VOLTAGE, precision=1),
    _f32("voltage_ph_n_l1", "Voltage L1-N", 1, "V", VOLTAGE, precision=1),
    _f32("voltage_ph_n_l2", "Voltage L2-N", 3, "V", VOLTAGE, precision=1),
    _f32("voltage_ph_n_l3", "Voltage L3-N", 5, "V", VOLTAGE, precision=1),
    _f32("voltage_ph_ph_l1_l2", "Voltage L1-L2", 7, "V", VOLTAGE, precision=1),
    _f32("voltage_ph_ph_l2_l3", "Voltage L2-L3", 9, "V", VOLTAGE, precision=1),
    _f32("voltage_ph_ph_l3_l1", "Voltage L3-L1", 11, "V", VOLTAGE, precision=1),
)


PAC2200_SENSOR_KEYS = {description.key for description in PAC2200_SENSORS}
