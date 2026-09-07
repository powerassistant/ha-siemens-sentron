"""Sensor platform for Siemens SENTRON."""

from __future__ import annotations

from dataclasses import dataclass
import math

from homeassistant.components.sensor import RestoreSensor, SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EntityCategory, UnitOfTime
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.restore_state import RestoreEntity
from homeassistant.helpers.update_coordinator import CoordinatorEntity
import homeassistant.util.dt as dt_util
from datetime import datetime

from .const import (
    DOMAIN,
    ECPD_SWITCH_VARIANTS,
    RCM_TEST_VARIANTS,
    GATEWAY_DEVICE_KEY,
    MANUFACTURER,
    get_device_configuration_url,
    SLAVES_KEY,
    VALUES_KEY,
)
from .coordinator import SentronCoordinator
from .device_types import (
    DEVICE_KIND_PAC2200,
    DEVICE_KIND_POWERCENTER,
    DEVICE_KIND_VERSICHARGE,
    is_versicharge_root,
)
from .entity_ids import SentronEntityIdMixin
from .pac2200 import PAC2200_SENSORS, PAC2200_SLAVE_ID, Pac2200SensorDescription
from .profiles import get_effective_device_profile
from .versicharge import VERSICHARGE_SENSORS, VersiChargeSensorDescription


SENSOR_ICONS = {
    # Quantities with an exact Home Assistant device class intentionally do not
    # appear here; their standard icon is supplied by Home Assistant.
    "reactive_power": "mdi:flash-outline",
    "frequency": "mdi:sine-wave",
    "power_factor": "mdi:angle-acute",
    "operating_hours_overall": "mdi:timer-outline",
    "radio_signal_strength_rssi": "mdi:signal",
    "leakage": "mdi:current-ac",
    "rcm_ac_low_pass": "mdi:current-ac",
    "rcm_rms_low_pass": "mdi:current-ac",
    "rcm_ac_basic_frequency": "mdi:current-ac",
    "firmware": "mdi:chip",
    "breaker_state": "mdi:electric-switch",
    "rca_handle_state": "mdi:electric-switch",
    "connection_state": "mdi:lan-pending",
    "alarm_state": "mdi:alert",
    "last_state_rcd_test": "mdi:clipboard-check-outline",
    "device_test_status": "mdi:clipboard-check-outline",
    "device_test_timestamp": "mdi:clock-check-outline",
    "rcm_test_status": "mdi:clipboard-check-outline",
    "rcm_test_timestamp": "mdi:clock-check-outline",
    "dido_input_1": "mdi:electric-switch",
    "dido_input_2": "mdi:electric-switch",
    "output_1_forcing": "mdi:source-branch",
    "output_2_forcing": "mdi:source-branch",
    "alarm_trip_active": "mdi:alert-circle-outline",
    "alarm_rcm_active": "mdi:current-ac",
    "alarm_manual_off_active": "mdi:electric-switch",
    "attached_device_type": "mdi:devices",
    "unlock_status": "mdi:lock-outline",
}


SENSOR_PRECISION = {
    "active_power": 0,
    "apparent_power": 0,
    "reactive_power": 0,
    "voltage": 1,
    "current": 2,
    "frequency": 2,
    "power_factor": 3,
    "temperature": 1,
    "average_temperature": 1,
    "operating_hours_overall": 1,
    "radio_signal_strength_rssi": 0,
    "ble_signal_strength_rssi": 0,
    "energy_import": 3,
    "energy_export": 3,
    "leakage": 1,
    "rcm_ac_low_pass": 1,
    "rcm_rms_low_pass": 1,
    "rcm_ac_basic_frequency": 1,
}

TEST_TIMESTAMP_FORMAT = "%d.%m.%Y %H:%M"


def _format_test_timestamp(value) -> str | None:
    """Format native/derived test timestamp as stable text, not HA relative time."""
    if value is None:
        return None
    try:
        local_value = dt_util.as_local(value)
    except (AttributeError, TypeError, ValueError):
        return None
    return local_value.strftime(TEST_TIMESTAMP_FORMAT)


def _parse_test_timestamp(value: str):
    """Parse restored text timestamp back into a datetime for display cache."""
    if not value or value in ("unknown", "unavailable"):
        return None
    parsed = dt_util.parse_datetime(value)
    if parsed is not None:
        return parsed
    try:
        naive = dt_util.dt.datetime.strptime(value, TEST_TIMESTAMP_FORMAT)
    except (TypeError, ValueError):
        return None
    if hasattr(dt_util.DEFAULT_TIME_ZONE, "localize"):
        return dt_util.as_utc(dt_util.DEFAULT_TIME_ZONE.localize(naive))
    return dt_util.as_utc(naive.replace(tzinfo=dt_util.DEFAULT_TIME_ZONE))


@dataclass
class GatewaySensorDescription:
    key: str
    name: str
    entity_category: EntityCategory | None = None
    icon: str | None = None
    unit: str | None = None
    device_class: str | None = None
    state_class: str | None = None


GATEWAY_SENSORS = [
    GatewaySensorDescription("firmware", "Firmware", EntityCategory.DIAGNOSTIC, "mdi:chip"),
    GatewaySensorDescription("variant", "Device Variant", EntityCategory.DIAGNOSTIC, "mdi:identifier"),
    GatewaySensorDescription("manufacturer_id", "Manufacturer ID", EntityCategory.DIAGNOSTIC, "mdi:factory"),
    GatewaySensorDescription("discovered_devices", "Erkannte Geräte", EntityCategory.DIAGNOSTIC, "mdi:devices"),
    GatewaySensorDescription("alarm_state", "Alarmzustand", None, SENSOR_ICONS["alarm_state"]),
    GatewaySensorDescription("operating_hours_overall", "Betriebsstunden Gesamt", EntityCategory.DIAGNOSTIC, SENSOR_ICONS["operating_hours_overall"], "h", None, "total_increasing"),
    GatewaySensorDescription("ble_signal_strength_rssi", "BLE Funksignal RSSI", EntityCategory.DIAGNOSTIC, SENSOR_ICONS["radio_signal_strength_rssi"], "dBm", None, "measurement"),
    GatewaySensorDescription("radio_channel", "Funkkanal", EntityCategory.DIAGNOSTIC, "mdi:radio-tower"),
    GatewaySensorDescription("temperature", "Internal Device Temperature", None, None, "°C", "temperature", "measurement"),
    GatewaySensorDescription("average_temperature", "Internal Device Temperature Average", None, None, "°C", "temperature", "measurement"),
]


# PAC2200 keeps its own minimal gateway-level identification diagnostics.
# Powercenter gateways intentionally do not expose PAC2200 I&M0-only fields
# such as article number, serial number, hardware revision, or profile ID.
PAC2200_GATEWAY_SENSORS = [
    GatewaySensorDescription("firmware", "Firmware", EntityCategory.DIAGNOSTIC, "mdi:chip"),
    GatewaySensorDescription("variant", "Device Variant", EntityCategory.DIAGNOSTIC, "mdi:identifier"),
    GatewaySensorDescription("manufacturer_id", "Manufacturer ID", EntityCategory.DIAGNOSTIC, "mdi:factory"),
    GatewaySensorDescription("order_id", "Artikelnummer", EntityCategory.DIAGNOSTIC, "mdi:barcode"),
]


def _gateway_sensors_for_device_kind(device_kind: str | None) -> list[GatewaySensorDescription]:
    if device_kind == DEVICE_KIND_PAC2200:
        return PAC2200_GATEWAY_SENSORS
    if device_kind == DEVICE_KIND_POWERCENTER:
        return GATEWAY_SENSORS
    return []


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    coordinator: SentronCoordinator = hass.data[DOMAIN][entry.entry_id]

    entities: list[SensorEntity] = []

    gateway = coordinator.data.get(GATEWAY_DEVICE_KEY, {})
    device_kind = gateway.get("device_kind")

    if is_versicharge_root(gateway):
        entities.extend(
            VersiChargeSensorEntity(coordinator, entry, description)
            for description in VERSICHARGE_SENSORS
        )
    elif device_kind == DEVICE_KIND_PAC2200:
        entities.extend(
            GatewaySensorEntity(coordinator, entry, description)
            for description in _gateway_sensors_for_device_kind(device_kind)
        )
        entities.extend(
            Pac2200SensorEntity(coordinator, entry, description)
            for description in PAC2200_SENSORS
        )
    elif device_kind == DEVICE_KIND_POWERCENTER:
        entities.extend(
            GatewaySensorEntity(coordinator, entry, description)
            for description in _gateway_sensors_for_device_kind(device_kind)
        )
        entities.append(PowercenterWriteCooldownSensorEntity(coordinator, entry))

        for slave_info in coordinator.data.get(SLAVES_KEY, []):
            profile = get_effective_device_profile(slave_info)
            for item in profile:
                entities.append(ProfileSensorEntity(coordinator, entry, slave_info, item))

            if slave_info.get("variant") in ECPD_SWITCH_VARIANTS:
                entities.append(EcpdStandbyCooldownSensorEntity(coordinator, entry, slave_info))
                entities.append(EcpdUnlockAcknowledgeSensorEntity(coordinator, entry, slave_info))
                # The composed ECPD sensor "Test Status Self-RCD" is intentionally
                # not created anymore. Keep the native profile entities
                # device_test_status and device_test_timestamp available, but avoid
                # the duplicate/generated sensor on ECPD devices.

            entities.append(SlavePowercenterWriteCooldownSensorEntity(coordinator, entry, slave_info))

            # 5SL6 COM MCB RCM keeps native diagnostic entities
            # "Test letztes Ergebnis (RCM)" and "Test letzter Zeitstempel (RCM)".
            # The composed/duplicate entity "Test Status RCM" intentionally stays disabled.
            entities.append(SlaveVariantSensorEntity(coordinator, entry, slave_info))
            entities.append(SlaveAddressSensorEntity(coordinator, entry, slave_info))

    async_add_entities(entities)


class SentronBaseEntity(SentronEntityIdMixin, CoordinatorEntity[SentronCoordinator]):
    _attr_has_entity_name = True

    def __init__(self, coordinator: SentronCoordinator, entry: ConfigEntry) -> None:
        super().__init__(coordinator)
        self.entry = entry

    @property
    def gateway_device_info(self) -> DeviceInfo:
        gateway = self.coordinator.data[GATEWAY_DEVICE_KEY]
        hardware_revision = gateway.get("hardware_revision")
        return DeviceInfo(
            identifiers={(DOMAIN, gateway["id"])},
            manufacturer=MANUFACTURER,
            model=gateway["model"],
            name=gateway["name"],
            sw_version=gateway["firmware"],
            hw_version=(
                str(hardware_revision) if hardware_revision is not None else None
            ),
            serial_number=gateway.get("serial_number"),
            configuration_url=get_device_configuration_url(gateway, gateway=gateway, prefer_local=True),
        )


class VersiChargeSensorEntity(SentronBaseEntity, RestoreSensor):
    """Sensor belonging directly to the standalone VersiCharge root."""

    def __init__(
        self,
        coordinator: SentronCoordinator,
        entry: ConfigEntry,
        description: VersiChargeSensorDescription,
    ) -> None:
        super().__init__(coordinator, entry)
        gateway = coordinator.data[GATEWAY_DEVICE_KEY]
        if not is_versicharge_root(gateway):
            raise ValueError("VersiCharge sensor requires a VersiCharge root")

        self.description = description
        self._unit_id = int(gateway["unit_id"])
        self._attr_translation_key = description.translation_key
        self._attr_unique_id = f"{entry.entry_id}_versicharge_{description.key}"
        self._attr_native_unit_of_measurement = description.unit
        self._attr_device_class = description.device_class
        self._attr_state_class = description.state_class
        self._attr_icon = description.icon
        self._attr_entity_registry_enabled_default = description.enabled_default
        self._attr_entity_category = (
            EntityCategory.DIAGNOSTIC if description.diagnostic else None
        )
        if description.precision is not None:
            self._attr_suggested_display_precision = description.precision
        if description.options is not None:
            self._attr_options = list(description.options)

    async def async_added_to_hass(self) -> None:
        """Restore the last cumulative energy before publishing a reset glitch."""
        await super().async_added_to_hass()
        if self.description.key != "energy_total":
            return
        restored_data = await self.async_get_last_sensor_data()
        if restored_data is None:
            return
        if (
            restored_data.native_unit_of_measurement
            != self.native_unit_of_measurement
        ):
            return
        try:
            restored = float(restored_data.native_value)
        except (TypeError, ValueError):
            return
        if not math.isfinite(restored) or restored < 0:
            return
        self.coordinator.restore_versicharge_energy(restored)

    @property
    def device_info(self) -> DeviceInfo:
        return self.gateway_device_info

    @property
    def available(self) -> bool:
        gateway = self.coordinator.data.get(GATEWAY_DEVICE_KEY, {})
        return (
            self.coordinator.last_update_success
            and gateway.get("device_kind") == DEVICE_KIND_VERSICHARGE
            and self._unit_id in self.coordinator.data.get(VALUES_KEY, {})
        )

    @property
    def native_value(self):
        value = self.coordinator.data.get(VALUES_KEY, {}).get(self._unit_id, {}).get(
            self.description.key
        )
        if isinstance(value, float) and not math.isfinite(value):
            return None
        return value

    @property
    def extra_state_attributes(self) -> dict[str, object] | None:
        values = self.coordinator.data.get(VALUES_KEY, {}).get(self._unit_id, {})
        if self.description.key == "evse_state":
            return {"raw_state": values.get("evse_state_raw")}
        if self.description.key == "ocpp_state":
            return {"raw_state": values.get("ocpp_state_raw")}
        if self.description.key == "error":
            return {
                "error_code": values.get("error_code"),
                "recoverable": values.get("error_recoverable"),
            }
        if self.description.key == "charging_current_limit":
            return {
                "raw_register_value": values.get("charging_current_limit_raw"),
                "readback_fresh": values.get(
                    "charging_current_limit_fresh", False
                ),
            }
        return None

def _format_alarm_state(value) -> str | None:
    """Format the common 32-bit alarm-state bitfield."""
    if value is None:
        return None
    if not isinstance(value, int):
        return value
    alarm_bits = {
        0: "Betriebsstunden mit Laststrom Alarm",
        1: "Betriebsstunden Alarm",
        2: "Mechanische Schaltspiele Alarm",
        3: "Auslösezähler Alarm",
        4: "Temperaturalarm",
        5: "Überstrom Alarm 1",
        6: "Überstrom Alarm 2",
        7: "Unterstrom Alarm 1",
        8: "Unterstrom Alarm 2",
        9: "Überspannung Alarm 1",
        10: "Überspannung Alarm 2",
        11: "Unterspannung Alarm 1",
        12: "Unterspannung Alarm 2",
        13: "Schalter ausgelöst",
        14: "Arc Fault Trip",
        15: "Überspannung Trip",
        16: "Kurzschlussauslösung Zähleralarm",
        17: "AFDD Trip Grenzwert aktiv",
        18: "Selbsttest fehlgeschlagen",
        19: "Unterspannung Trip",
        20: "Residual Current Trip",
        24: "RCM Voralarm",
        25: "RCM Alarm",
        26: "Zeitverzögerte Auslösung Überstrom",
        27: "Sofortauslösung Überstrom",
        28: "ARD fehlgeschlagen",
        29: "Übertemperatur Trip",
        30: "Zeitverzögerte Auslöseschwelle Alarm",
        31: "Einschalten blockiert",
    }
    active = [label for bit, label in alarm_bits.items() if value & (1 << bit)]
    return ", ".join(active) if active else "Kein Alarm aktiv"


def _format_pac2200_binary_state(value) -> str | None:
    if value is None:
        return None
    if not isinstance(value, int):
        return value
    return "On" if value & 0x00000001 else "Off"


def _format_pac2200_tariff(value) -> str | None:
    if value is None:
        return None
    if not isinstance(value, int):
        return value
    return {0: "Tariff 1", 1: "Tariff 2"}.get(value, f"Unknown ({value})")


def _format_pac2200_diagnostics(value) -> str | None:
    if value is None:
        return None
    if not isinstance(value, int):
        return value

    status_bits = {
        24: "No synchronization pulse",
        25: "Device configuration menu active",
        26: "Voltage overload",
        27: "Current overload",
        29: "Update status active",
        30: "Hardware write protection active",
        31: "Modbus communication write-protected",
        17: "Maximum pulse rate exceeded",
        22: "SNTP not synchronized",
        23: "Wait for user interaction",
        8: "Relevant parameter changes",
        10: "Maximum pulse rate exceeded",
        11: "Restart of the device",
        12: "Energy counter reset by user",
    }
    active = [label for bit, label in status_bits.items() if value & (1 << bit)]
    return ", ".join(active) if active else "OK"


def _format_pac2200_datetime(value) -> str | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        return dt_util.as_local(value).strftime("%d.%m.%Y %H:%M:%S")
    return value


class Pac2200SensorEntity(SentronBaseEntity, SensorEntity):
    """Sensor entity for the standalone PAC2200 root device."""

    def __init__(
        self,
        coordinator: SentronCoordinator,
        entry: ConfigEntry,
        description: Pac2200SensorDescription,
    ) -> None:
        super().__init__(coordinator, entry)
        self.description = description
        self._attr_translation_key = description.key
        self._attr_unique_id = f"{entry.entry_id}_pac2200_{description.key}"
        self._attr_native_unit_of_measurement = description.unit
        self._attr_device_class = description.device_class
        self._attr_state_class = description.state_class
        self._attr_icon = None if description.device_class else (description.icon or SENSOR_ICONS.get(description.key))
        self._attr_entity_category = description.entity_category
        self._attr_entity_registry_enabled_default = description.enabled_default
        if description.precision is not None:
            self._attr_suggested_display_precision = description.precision

    @property
    def device_info(self) -> DeviceInfo:
        return self.gateway_device_info

    @property
    def native_value(self):
        values = self.coordinator.data.get(VALUES_KEY, {})
        value = values.get(PAC2200_SLAVE_ID, {}).get(self.description.key)

        if isinstance(value, float) and not math.isfinite(value):
            return None

        if self.description.key == "actual_tariff":
            return _format_pac2200_tariff(value)
        if self.description.key in ("state_binary_inputs", "state_binary_outputs"):
            return _format_pac2200_binary_state(value)
        if self.description.key == "device_diagnostics_status":
            return _format_pac2200_diagnostics(value)
        if self.description.key == "date_time":
            return _format_pac2200_datetime(value)

        if isinstance(value, float) and self.description.precision is not None:
            return round(value, self.description.precision)

        return value



class GatewaySensorEntity(SentronBaseEntity, SensorEntity):
    def __init__(
        self,
        coordinator: SentronCoordinator,
        entry: ConfigEntry,
        description: GatewaySensorDescription,
    ) -> None:
        super().__init__(coordinator, entry)
        self.description = description
        self._attr_translation_key = description.key
        self._attr_unique_id = f"{entry.entry_id}_gateway_{description.key}"
        self._attr_entity_category = description.entity_category
        self._attr_icon = None if description.device_class else description.icon
        self._attr_native_unit_of_measurement = description.unit
        self._attr_device_class = description.device_class
        self._attr_state_class = description.state_class
        if description.key in SENSOR_PRECISION:
            self._attr_suggested_display_precision = SENSOR_PRECISION[description.key]
        self._attr_entity_registry_enabled_default = description.key != "manufacturer_id"

    @property
    def device_info(self) -> DeviceInfo:
        return self.gateway_device_info

    @property
    def native_value(self):
        gateway = self.coordinator.data[GATEWAY_DEVICE_KEY]
        if self.description.key == "discovered_devices":
            return len(self.coordinator.data.get(SLAVES_KEY, []))
        value = gateway.get(self.description.key)
        if isinstance(value, float) and not math.isfinite(value):
            return None
        if self.description.key == "alarm_state":
            return _format_alarm_state(value)
        if isinstance(value, float) and self.description.key in SENSOR_PRECISION:
            return round(value, SENSOR_PRECISION[self.description.key])
        return value


class PowercenterWriteCooldownSensorEntity(SentronBaseEntity, SensorEntity):
    """Visible per-gateway delayed-ACK write/command cooldown countdown."""

    def __init__(self, coordinator: SentronCoordinator, entry: ConfigEntry) -> None:
        super().__init__(coordinator, entry)
        self._attr_translation_key = "powercenter_write_cooldown"
        self._attr_unique_id = f"{entry.entry_id}_gateway_powercenter_write_cooldown"
        self._attr_native_unit_of_measurement = UnitOfTime.SECONDS
        self._attr_entity_category = EntityCategory.DIAGNOSTIC
        self._attr_entity_registry_enabled_default = True
        self._attr_icon = "mdi:timer-check-outline"
        self._attr_suggested_display_precision = 0

    @property
    def device_info(self) -> DeviceInfo:
        return self.gateway_device_info

    @property
    def native_value(self):
        return self.coordinator.get_powercenter_write_cooldown_remaining()

    @property
    def icon(self) -> str:
        if self.coordinator.is_powercenter_write_cooldown_active():
            return "mdi:timer-sand"
        return "mdi:timer-check-outline"


class SlavePowercenterWriteCooldownSensorEntity(SentronBaseEntity, SensorEntity):
    """Visible Powercenter delayed-ACK cooldown countdown on each slave device."""

    def __init__(self, coordinator: SentronCoordinator, entry: ConfigEntry, slave_info: dict) -> None:
        super().__init__(coordinator, entry)
        self.slave = slave_info["slave"]
        self._attr_translation_key = "powercenter_write_cooldown"
        self._attr_unique_id = f"{entry.entry_id}_slave_{self.slave}_powercenter_write_cooldown"
        self._attr_native_unit_of_measurement = UnitOfTime.SECONDS
        self._attr_entity_category = EntityCategory.DIAGNOSTIC
        self._attr_entity_registry_enabled_default = True
        self._attr_suggested_display_precision = 0

    @property
    def slave_info(self) -> dict:
        for item in self.coordinator.data.get(SLAVES_KEY, []):
            if item["slave"] == self.slave:
                return item
        return {
            "slave": self.slave,
            "firmware": "Unknown",
            "name": f"{self.slave} - Unknown Device",
            "model": "SENTRON Unknown Device",
        }

    @property
    def device_info(self) -> DeviceInfo:
        info = self.slave_info
        gateway = self.coordinator.data[GATEWAY_DEVICE_KEY]
        return DeviceInfo(
            identifiers={(DOMAIN, f"{self.entry.entry_id}_slave_{self.slave}")},
            manufacturer=MANUFACTURER,
            model=info.get("model", "SENTRON Unknown Device"),
            name=info.get("name", f"{self.slave} - Unknown Device"),
            sw_version=info.get("firmware", "Unknown"),
            configuration_url=get_device_configuration_url(info),
            via_device_id=self.coordinator.gateway_device_registry_id,
        )

    @property
    def native_value(self):
        return self.coordinator.get_powercenter_write_cooldown_remaining()

    @property
    def available(self) -> bool:
        return self.coordinator.is_unit_connected(self.slave)

    @property
    def icon(self) -> str:
        if self.coordinator.is_powercenter_write_cooldown_active():
            return "mdi:timer-sand"
        return "mdi:timer-check-outline"


class SlaveBaseSensorEntity(SentronBaseEntity, SensorEntity):
    def __init__(
        self,
        coordinator: SentronCoordinator,
        entry: ConfigEntry,
        slave_info: dict,
    ) -> None:
        super().__init__(coordinator, entry)
        self.slave = slave_info["slave"]

    @property
    def available(self) -> bool:
        return self.coordinator.last_update_success

    @property
    def slave_info(self) -> dict:
        for item in self.coordinator.data.get(SLAVES_KEY, []):
            if item["slave"] == self.slave:
                return item
        return {
            "slave": self.slave,
            "variant": None,
            "firmware": "Unknown",
            "name": f"{self.slave} - Unknown Device",
            "device_type": "generic_sentron_device",
            "type_label": "Unknown Device",
            "model": "SENTRON Unknown Device",
        }

    @property
    def device_info(self) -> DeviceInfo:
        info = self.slave_info
        gateway = self.coordinator.data[GATEWAY_DEVICE_KEY]
        return DeviceInfo(
            identifiers={(DOMAIN, f"{self.entry.entry_id}_slave_{self.slave}")},
            manufacturer=MANUFACTURER,
            model=info.get("model", "SENTRON Unknown Device"),
            name=info.get("name", f"{self.slave} - Unknown Device"),
            sw_version=info.get("firmware", "Unknown"),
            configuration_url=get_device_configuration_url(info),
            via_device_id=self.coordinator.gateway_device_registry_id,
        )


class ProfileSensorEntity(SlaveBaseSensorEntity, RestoreEntity):
    def __init__(
        self,
        coordinator: SentronCoordinator,
        entry: ConfigEntry,
        slave_info: dict,
        profile_item: dict,
    ) -> None:
        super().__init__(coordinator, entry, slave_info)
        self.profile_item = profile_item
        self.key = profile_item["key"]
        self._attr_translation_key = self.key
        self._attr_unique_id = f"{entry.entry_id}_slave_{self.slave}_{self.key}"
        self._attr_native_unit_of_measurement = profile_item.get("unit")
        self._attr_device_class = profile_item.get("device_class")
        if self.key in ("device_test_timestamp", "rcm_test_timestamp"):
            # Text sensor by design: show the stored timestamp value itself,
            # not Home Assistant's relative "vor x Minuten" rendering.
            self._attr_device_class = None
        self._attr_state_class = profile_item.get("state_class")
        self._attr_entity_registry_enabled_default = profile_item.get("enabled_default", True)
        self._attr_icon = SENSOR_ICONS.get(self.key)

        if self.key in SENSOR_PRECISION:
            self._attr_suggested_display_precision = SENSOR_PRECISION[self.key]

        if profile_item.get("diagnostic"):
            self._attr_entity_category = EntityCategory.DIAGNOSTIC

    async def async_added_to_hass(self) -> None:
        """Restore locally derived RCM test timestamp after Home Assistant reload."""
        await super().async_added_to_hass()
        if self.key != "rcm_test_timestamp":
            return
        last_state = await self.async_get_last_state()
        if last_state is None or last_state.state in (None, "unknown", "unavailable"):
            return
        restored = _parse_test_timestamp(last_state.state)
        if restored is None:
            return
        self.coordinator.restore_test_display_values(
            self.slave,
            kind="rcm",
            status_key="rcm_test_status",
            timestamp_key="rcm_test_timestamp",
            timestamp_value=restored,
        )

    @property
    def available(self) -> bool:
        """Expose connectivity itself while hiding stale operational values."""
        values = self.coordinator.data.get(VALUES_KEY, {})
        if self.key == "connection_state":
            return (
                self.coordinator.last_update_success
                and values.get(self.slave, {}).get(self.key) is not None
            )
        return self.coordinator.is_unit_connected(self.slave)

    @property
    def native_value(self):
        values = self.coordinator.data.get(VALUES_KEY, {})
        value = values.get(self.slave, {}).get(self.key)

        # Test timestamp entities are stable text values in device/derived
        # timestamp format instead of Home Assistant relative timestamp sensors.
        if self.key == "device_test_timestamp":
            _result, native_timestamp = self.coordinator.get_test_display_values(
                self.slave,
                kind="ecpd",
                status_key="device_test_status",
                timestamp_key="device_test_timestamp",
            )
            return _format_test_timestamp(native_timestamp)

        if self.key == "rcm_test_timestamp":
            _result, derived_timestamp = self.coordinator.get_test_display_values(
                self.slave,
                kind="rcm",
                status_key="rcm_test_status",
                timestamp_key="rcm_test_timestamp",
            )
            return _format_test_timestamp(derived_timestamp)

        if isinstance(value, float) and not math.isfinite(value):
            return None

        if value is None and self.key == "firmware":
            return self.slave_info.get("firmware")

        if self.key == "attached_device_type":
            if value is None:
                value = self.slave_info.get("attached_device_type")
            if isinstance(value, int):
                return {
                    0: "Unknown",
                    1: "RCD",
                    2: "MCB",
                    3: "SCD",
                    4: "AFDD",
                    5: "RCBO",
                }.get(value, f"Unknown ({value})")
            return value

        if self.key == "alarm_state":
            if value is None:
                return None
            if not isinstance(value, int):
                return value
            active = []
            alarm_bits = {
                0: "Betriebsstunden mit Laststrom Alarm",
                1: "Betriebsstunden Alarm",
                2: "Mechanische Schaltspiele Alarm",
                3: "Auslösezähler Alarm",
                4: "Temperaturalarm",
                5: "Überstrom Alarm 1",
                6: "Überstrom Alarm 2",
                7: "Unterstrom Alarm 1",
                8: "Unterstrom Alarm 2",
                9: "Überspannung Alarm 1",
                10: "Überspannung Alarm 2",
                11: "Unterspannung Alarm 1",
                12: "Unterspannung Alarm 2",
                13: "Schalter ausgelöst",
                14: "Arc Fault Trip",
                15: "Überspannung Trip",
                16: "Kurzschlussauslösung Zähleralarm",
                17: "AFDD Trip Grenzwert aktiv",
                18: "Selbsttest fehlgeschlagen",
                19: "Unterspannung Trip",
                20: "Residual Current Trip",
                24: "RCM Voralarm",
                25: "RCM Alarm",
                26: "Zeitverzögerte Auslösung Überstrom",
                27: "Sofortauslösung Überstrom",
                28: "ARD fehlgeschlagen",
                29: "Übertemperatur Trip",
                30: "Zeitverzögerte Auslöseschwelle Alarm",
                31: "Einschalten blockiert",
            }
            for bit, label in alarm_bits.items():
                if value & (1 << bit):
                    active.append(label)
            return ", ".join(active) if active else "Kein Alarm aktiv"

        if self.key == "unlock_status":
            if value is None or not isinstance(value, int):
                return value
            return {
                0: "Locked",
                1: "Unlocked",
                2: "Ready for unlock",
                3: "Time almost expired",
            }.get(value, f"Unknown ({value})")

        if self.key == "last_state_rcd_test":
            if value is None or not isinstance(value, int):
                return value
            # Modbus map: 0 = unknown. Treat as no valid backend value.
            if value == 0:
                return None
            return {
                1: "RCD-Test bestanden",
                2: "Fehler: Hauptgerät nicht ausgelöst",
                3: "Fehler: Auslösezeit abnormal",
                4: "Fehler: Konfiguration",
                5: "Fehler: Handle State",
                6: "Fehler: gelber Mode Slider",
                7: "Fehler: Trip-Arm State",
                8: "Fehler: Hardware",
                9: "Test nicht ausgeführt",
                10: "Test abgebrochen",
                11: "RCD-Test fehlgeschlagen",
                12: "RCD-Test fehlgeschlagen: ARD-Konfiguration",
            }.get(value, f"Unknown ({value})")

        if self.key in ("dido_input_1", "dido_input_2"):
            if value is True:
                return "Aktiv"
            if value is False:
                return "Inaktiv"
            return None

        if self.key in ("output_1_state", "output_2_state"):
            if not isinstance(value, dict):
                return None
            return "Ein" if value.get("output_state") else "Aus"

        if self.key in ("output_1_forcing", "output_2_forcing"):
            if not isinstance(value, dict):
                return None
            source = {
                0: "Logikblock",
                1: "Befehl",
                2: "Taste",
            }.get(value.get("source"), f"Quelle {value.get('source')}")
            remaining = value.get("remaining_time_s")
            if remaining is None:
                return source
            return f"{source} / Restzeit {remaining} s"

        if self.key in (
            "alarm_trip_active",
            "alarm_rcm_active",
            "alarm_manual_off_active",
        ):
            if value is True:
                return "Aktiv"
            if value is False:
                return "Inaktiv"
            return None

        if isinstance(value, float) and self.key in SENSOR_PRECISION:
            return round(value, SENSOR_PRECISION[self.key])

        return value


    
    @property
    def icon(self) -> str | None:
        if self.key == "unlock_status":
            value = self.coordinator.data.get(VALUES_KEY, {}).get(self.slave, {}).get(self.key)
            if value in (1, 3):
                return "mdi:lock-open-variant-outline"
            return "mdi:lock-outline"
        return self._attr_icon


class TestStatusSensorEntity(SlaveBaseSensorEntity):
    """Combined test result and timestamp sensor."""

    def __init__(
        self,
        coordinator: SentronCoordinator,
        entry: ConfigEntry,
        slave_info: dict,
        *,
        status_key: str,
        timestamp_key: str,
        test_type: str,
        unique_suffix: str,
        test_kind: str,
    ) -> None:
        super().__init__(coordinator, entry, slave_info)
        self.status_key = status_key
        self.timestamp_key = timestamp_key
        self.test_type = test_type
        self.test_kind = test_kind
        self._attr_translation_key = "test_status_self_rcd" if test_kind == "ecpd" else "test_status_rcm"
        self._attr_unique_id = f"{entry.entry_id}_slave_{self.slave}_{unique_suffix}"
        self._attr_entity_registry_enabled_default = True
        self._attr_icon = "mdi:clipboard-pulse-outline"

    @property
    def native_value(self):
        result, timestamp = self.coordinator.get_test_display_values(
            self.slave,
            kind=self.test_kind,
            status_key=self.status_key,
            timestamp_key=self.timestamp_key,
        )

        if self.coordinator.is_device_test_running(self.slave, self.test_kind):
            return f"Test wird durchgeführt - {self.test_type}"

        if result is None:
            return None

        if timestamp is None:
            return f"{result} - {self.test_type}"

        timestamp_text = _format_test_timestamp(timestamp)
        if timestamp_text is None:
            return f"{result} - {self.test_type}"

        return f"{result} - {self.test_type} - {timestamp_text}"


class EcpdStandbyCooldownSensorEntity(SlaveBaseSensorEntity):
    """Visible ECPD standby cooldown countdown sensor."""

    def __init__(
        self,
        coordinator: SentronCoordinator,
        entry: ConfigEntry,
        slave_info: dict,
    ) -> None:
        super().__init__(coordinator, entry, slave_info)
        self._attr_translation_key = "standby_cooldown"
        self._attr_unique_id = f"{entry.entry_id}_slave_{self.slave}_standby_cooldown"
        self._attr_native_unit_of_measurement = UnitOfTime.SECONDS
        self._attr_entity_category = EntityCategory.DIAGNOSTIC
        self._attr_entity_registry_enabled_default = True
        self._attr_icon = "mdi:timer-check-outline"
        self._attr_suggested_display_precision = 0

    @property
    def native_value(self):
        return self.coordinator.get_ecpd_standby_cooldown_remaining(self.slave)


class EcpdUnlockAcknowledgeSensorEntity(SlaveBaseSensorEntity):
    """Visible ECPD unlock acknowledge countdown sensor."""

    def __init__(
        self,
        coordinator: SentronCoordinator,
        entry: ConfigEntry,
        slave_info: dict,
    ) -> None:
        super().__init__(coordinator, entry, slave_info)
        self._attr_translation_key = "unlock_acknowledge"
        self._attr_unique_id = f"{entry.entry_id}_slave_{self.slave}_unlock_acknowledge"
        self._attr_native_unit_of_measurement = UnitOfTime.SECONDS
        self._attr_entity_category = EntityCategory.DIAGNOSTIC
        self._attr_entity_registry_enabled_default = True
        self._attr_suggested_display_precision = 0

    @property
    def native_value(self):
        return self.coordinator.get_ecpd_unlock_ack_remaining(self.slave)

    @property
    def icon(self) -> str:
        status = self.coordinator.data.get(VALUES_KEY, {}).get(self.slave, {}).get("unlock_status")
        remaining = self.coordinator.get_ecpd_unlock_ack_remaining(self.slave)
        if status == 3 or (0 < remaining <= 15):
            return "mdi:timer-alert-outline"
        if remaining > 0:
            return "mdi:timer-sand"
        return "mdi:timer-off-outline"


class SlaveVariantSensorEntity(SlaveBaseSensorEntity):
    def __init__(
        self,
        coordinator: SentronCoordinator,
        entry: ConfigEntry,
        slave_info: dict,
    ) -> None:
        super().__init__(coordinator, entry, slave_info)
        self._attr_translation_key = "variant"
        self._attr_unique_id = f"{entry.entry_id}_slave_{self.slave}_variant"
        self._attr_entity_category = EntityCategory.DIAGNOSTIC
        self._attr_entity_registry_enabled_default = True
        self._attr_icon = "mdi:identifier"

    @property
    def native_value(self):
        return self.slave_info.get("variant")


class SlaveAddressSensorEntity(SlaveBaseSensorEntity):
    def __init__(
        self,
        coordinator: SentronCoordinator,
        entry: ConfigEntry,
        slave_info: dict,
    ) -> None:
        super().__init__(coordinator, entry, slave_info)
        self._attr_translation_key = "unit_id"
        self._attr_unique_id = f"{entry.entry_id}_slave_{self.slave}_address"
        self._attr_entity_category = EntityCategory.DIAGNOSTIC
        self._attr_entity_registry_enabled_default = True
        self._attr_icon = "mdi:identifier"

    @property
    def native_value(self):
        return self.slave

class SlaveOnlineSensorEntity(SentronBaseEntity, SensorEntity):
    def __init__(
        self,
        coordinator: SentronCoordinator,
        entry: ConfigEntry,
        slave_info: dict,
    ) -> None:
        super().__init__(coordinator, entry)
        self.slave = slave_info["slave"]
        self._attr_translation_key = "online_status"
        self._attr_unique_id = f"{entry.entry_id}_slave_{self.slave}_online_status"
        self._attr_entity_category = EntityCategory.DIAGNOSTIC
        self._attr_entity_registry_enabled_default = True
        self._attr_icon = "mdi:lan-connect"

    @property
    def available(self) -> bool:
        return True

    @property
    def slave_info(self) -> dict:
        for item in self.coordinator.data.get(SLAVES_KEY, []):
            if item["slave"] == self.slave:
                return item
        return {
            "slave": self.slave,
            "variant": None,
            "firmware": "Unknown",
            "name": f"{self.slave} - Unknown Device",
            "device_type": "generic_sentron_device",
            "type_label": "Unknown Device",
            "model": "SENTRON Unknown Device",
            "online": False,
        }

    @property
    def device_info(self) -> DeviceInfo:
        info = self.slave_info
        gateway = self.coordinator.data[GATEWAY_DEVICE_KEY]
        return DeviceInfo(
            identifiers={(DOMAIN, f"{self.entry.entry_id}_slave_{self.slave}")},
            manufacturer=MANUFACTURER,
            model=info.get("model", "SENTRON Unknown Device"),
            name=info.get("name", f"{self.slave} - Unknown Device"),
            sw_version=info.get("firmware", "Unknown"),
            configuration_url=get_device_configuration_url(info),
            via_device_id=self.coordinator.gateway_device_registry_id,
        )

    @property
    def native_value(self):
        if self.slave_info.get("online", False):
            return "Online"
        return "Offline"
