"""Number platform for Siemens SENTRON writable configuration."""

from __future__ import annotations

from homeassistant.components.number import NumberDeviceClass, NumberEntity, NumberMode
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    EntityCategory,
    PERCENTAGE,
    UnitOfElectricCurrent,
    UnitOfPower,
    UnitOfTime,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN, ECPD_SWITCH_VARIANTS, MCB_RCM_VARIANTS, GATEWAY_DEVICE_KEY, MANUFACTURER, get_device_configuration_url, SLAVES_KEY, VALUES_KEY
from .coordinator import SentronCoordinator
from .device_types import is_versicharge_root
from .entity_ids import SentronEntityIdMixin
from .versicharge import (
    VERSICHARGE_MIN_CURRENT,
    active_phase_count,
    nominal_power_bounds_kw,
)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback) -> None:
    coordinator: SentronCoordinator = hass.data[DOMAIN][entry.entry_id]
    entities: list[NumberEntity] = []
    gateway = coordinator.data.get(GATEWAY_DEVICE_KEY, {})
    if is_versicharge_root(gateway):
        entities.extend(
            (
                VersiChargeChargingPowerNumber(coordinator, entry),
                VersiChargeFallbackCurrentNumber(coordinator, entry),
                VersiChargeFallbackTimeNumber(coordinator, entry),
            )
        )
    for slave_info in coordinator.data.get(SLAVES_KEY, []):
        if slave_info.get("variant") in ECPD_SWITCH_VARIANTS:
            entities.append(EcpdRcmThresholdNumber(coordinator, entry, slave_info, pre_alarm=True))
            entities.append(EcpdRcmThresholdNumber(coordinator, entry, slave_info, pre_alarm=False))
        if slave_info.get("variant") in MCB_RCM_VARIANTS:
            entities.append(McbRcmThresholdNumber(coordinator, entry, slave_info, pre_alarm=True))
            entities.append(McbRcmThresholdNumber(coordinator, entry, slave_info, pre_alarm=False))
    async_add_entities(entities)


class VersiChargeNumberEntity(
    SentronEntityIdMixin, CoordinatorEntity[SentronCoordinator], NumberEntity
):
    """Base for disabled-by-default VersiCharge root controls."""

    _attr_has_entity_name = True
    _attr_entity_category = EntityCategory.CONFIG
    _attr_entity_registry_enabled_default = False
    _attr_mode = NumberMode.BOX

    def __init__(
        self, coordinator: SentronCoordinator, entry: ConfigEntry, key: str
    ) -> None:
        super().__init__(coordinator)
        self.entry = entry
        self._attr_translation_key = key
        self._attr_unique_id = f"{entry.entry_id}_{key}"

    @property
    def available(self) -> bool:
        gateway = self.coordinator.data.get(GATEWAY_DEVICE_KEY, {}) if self.coordinator.data else {}
        return self.coordinator.last_update_success and is_versicharge_root(gateway)

    @property
    def device_info(self) -> DeviceInfo:
        gateway = self.coordinator.data[GATEWAY_DEVICE_KEY]
        return DeviceInfo(
            identifiers={(DOMAIN, gateway["id"])},
            manufacturer=MANUFACTURER,
            model=gateway["model"],
            name=gateway["name"],
            sw_version=gateway.get("firmware"),
            serial_number=gateway.get("serial_number"),
            configuration_url=get_device_configuration_url(
                gateway, gateway=gateway, prefer_local=True
            ),
        )

    @property
    def _values(self) -> dict:
        return self.coordinator.get_versicharge_values()


class VersiChargeTargetNumberEntity(VersiChargeNumberEntity):
    """Base that prevents telemetry polls from redrawing an editable box."""

    def __init__(
        self, coordinator: SentronCoordinator, entry: ConfigEntry, key: str
    ) -> None:
        super().__init__(coordinator, entry, key)
        self._last_presentation_signature: tuple[object, ...] | None = None

    async def async_added_to_hass(self) -> None:
        """Remember the initially published control state."""
        await super().async_added_to_hass()
        self._last_presentation_signature = self._presentation_signature()

    def _presentation_signature(self) -> tuple[object, ...]:
        raise NotImplementedError

    @callback
    def _handle_coordinator_update(self) -> None:
        """Publish target/capability changes, not volatile measurements."""
        signature = self._presentation_signature()
        if signature == self._last_presentation_signature:
            return
        self._last_presentation_signature = signature
        self.async_write_ha_state()


class VersiChargeChargingPowerNumber(VersiChargeTargetNumberEntity):
    """Single 0.1-kW target converted once to a whole-ampere limit."""

    _attr_device_class = NumberDeviceClass.POWER
    _attr_native_unit_of_measurement = UnitOfPower.KILO_WATT
    _attr_native_step = 0.1

    def __init__(self, coordinator: SentronCoordinator, entry: ConfigEntry) -> None:
        super().__init__(coordinator, entry, "versicharge_charging_power")

    def _presentation_signature(self) -> tuple[object, ...]:
        """Return only changes that should redraw the editable number box.

        Voltage, power factor, actual power and register freshness are
        deliberately excluded. They remain read-only measurements and can
        neither alter this user target nor trigger a command.
        """
        try:
            values = self._values
            return (
                self.available,
                self.coordinator.versicharge_target_power_kw,
                active_phase_count(values),
                self.coordinator.versicharge_installation_current,
                self._power_bounds,
            )
        except (HomeAssistantError, KeyError):
            return (False, None, None, None, None)

    @property
    def available(self) -> bool:
        return (
            super().available
            and self.coordinator.versicharge_current_control_available
            and self._power_bounds is not None
        )

    @property
    def _power_bounds(self) -> tuple[float, float] | None:
        return nominal_power_bounds_kw(
            self._values, self.coordinator.versicharge_installation_current
        )

    @property
    def native_min_value(self) -> float:
        bounds = self._power_bounds
        return float(bounds[0]) if bounds is not None else 0.0

    @property
    def native_max_value(self) -> float:
        bounds = self._power_bounds
        return float(bounds[1]) if bounds is not None else 0.0

    @property
    def native_value(self) -> float | None:
        value = self.coordinator.versicharge_target_power_kw
        return round(value, 1) if value is not None else None

    @property
    def extra_state_attributes(self) -> dict[str, object]:
        return {
            "derived_current_a": self.coordinator.versicharge_target_current,
            "active_phases": active_phase_count(self._values),
            "conversion": "kW / (230 V × active phases), rounded to whole A",
            "current_command_resolution_a": 1,
            "modbus_register": 1633,
        }

    async def async_set_native_value(self, value: float) -> None:
        await self.coordinator.async_set_versicharge_target_power_kw(value)


class VersiChargeFallbackCurrentNumber(VersiChargeNumberEntity):
    """Charger-native current after Modbus supervision expires."""

    _attr_device_class = NumberDeviceClass.CURRENT
    _attr_native_unit_of_measurement = UnitOfElectricCurrent.AMPERE
    _attr_native_min_value = 0
    _attr_native_step = 1

    def __init__(self, coordinator: SentronCoordinator, entry: ConfigEntry) -> None:
        super().__init__(coordinator, entry, "versicharge_fallback_current")

    @property
    def native_max_value(self) -> float:
        return float(self.coordinator.versicharge_installation_current)

    @property
    def native_value(self) -> float | None:
        value = self._values.get("fallback_current")
        return float(value) if isinstance(value, int) else None

    @property
    def available(self) -> bool:
        return super().available and self.native_value is not None

    @property
    def extra_state_attributes(self) -> dict[str, object]:
        return {
            "valid_values": f"0 or {VERSICHARGE_MIN_CURRENT}..{self.native_max_value:g} A",
            "non_persistent": True,
            "recommended_for_pv_only_a": 0,
        }

    async def async_set_native_value(self, value: float) -> None:
        if not float(value).is_integer():
            raise HomeAssistantError("Fallback current must be a whole ampere")
        await self.coordinator.async_set_versicharge_fallback(current=int(value))


class VersiChargeFallbackTimeNumber(VersiChargeNumberEntity):
    """Charger-native Modbus-loss timeout."""

    _attr_device_class = NumberDeviceClass.DURATION
    _attr_native_unit_of_measurement = UnitOfTime.SECONDS
    _attr_native_min_value = 0
    _attr_native_max_value = 600
    _attr_native_step = 1

    def __init__(self, coordinator: SentronCoordinator, entry: ConfigEntry) -> None:
        super().__init__(coordinator, entry, "versicharge_fallback_time")

    @property
    def native_value(self) -> float | None:
        value = self._values.get("fallback_time")
        return float(value) if isinstance(value, int) else None

    @property
    def available(self) -> bool:
        return super().available and self.native_value is not None

    @property
    def extra_state_attributes(self) -> dict[str, object]:
        return {
            "valid_values": "0 or 60..600 s",
            "non_persistent": True,
            "recommended_for_pv_control_s": 60,
        }

    async def async_set_native_value(self, value: float) -> None:
        if not float(value).is_integer():
            raise HomeAssistantError("Fallback time must be whole seconds")
        await self.coordinator.async_set_versicharge_fallback(timeout=int(value))


class EcpdRcmThresholdNumber(SentronEntityIdMixin, CoordinatorEntity[SentronCoordinator], NumberEntity):
    _attr_has_entity_name = True
    _attr_entity_category = EntityCategory.CONFIG
    _attr_mode = NumberMode.BOX
    _attr_entity_registry_enabled_default = False

    def __init__(self, coordinator: SentronCoordinator, entry: ConfigEntry, slave_info: dict, *, pre_alarm: bool) -> None:
        super().__init__(coordinator)
        self.entry = entry
        self.slave = slave_info["slave"]
        self.coordinator.register_powercenter_guarded_entity(self)
        self.pre_alarm = pre_alarm
        self._last_valid_value: int | None = None
        if pre_alarm:
            self._attr_translation_key = "rcm_ac_pre_alarm_threshold"
            self._attr_unique_id = f"{entry.entry_id}_slave_{self.slave}_rcm_ac_pre_alarm_threshold"
            self._attr_native_min_value = 50
            self._attr_native_max_value = 100
            self._attr_native_step = 1
            self._attr_native_unit_of_measurement = PERCENTAGE
            self._value_key = "rcm_ac_pre_alarm_threshold_percent"
            self._write_address = 5136  # register 5137 - offset 1
        else:
            self._attr_translation_key = "rcm_ac_alarm_threshold"
            self._attr_unique_id = f"{entry.entry_id}_slave_{self.slave}_rcm_ac_alarm_threshold"
            self._attr_native_min_value = 3
            self._attr_native_max_value = 30
            self._attr_native_step = 1
            self._attr_native_unit_of_measurement = UnitOfElectricCurrent.MILLIAMPERE
            self._value_key = "rcm_ac_alarm_threshold_ma"
            self._write_address = 5138  # register 5139 - offset 1

    @property
    def slave_info(self) -> dict:
        for item in self.coordinator.data.get(SLAVES_KEY, []):
            if item["slave"] == self.slave:
                return item
        return {"slave": self.slave, "firmware": "Unknown", "name": f"{self.slave} - Unknown Device", "model": "SENTRON Unknown Device"}

    @property
    def available(self) -> bool:
        return (
            self.coordinator.is_unit_connected(self.slave)
            and not self.coordinator.should_block_powercenter_interaction(
                slave=self.slave
            )
        )

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
        value = self.coordinator.data.get(VALUES_KEY, {}).get(self.slave, {}).get(self._value_key)
        if isinstance(value, (int, float)):
            ui_value = int(round(float(value)))
            if self.native_min_value <= ui_value <= self.native_max_value:
                self._last_valid_value = ui_value
                return ui_value

        # Keep the last value that was actually read, but never fabricate a
        # writable device setting before the first successful read.
        return self._last_valid_value

    @property
    def extra_state_attributes(self) -> dict[str, float | str]:
        unit = self.native_unit_of_measurement or ""
        return {
            "allowed_min": self.native_min_value,
            "allowed_max": self.native_max_value,
            "allowed_range": f"{self.native_min_value:g}-{self.native_max_value:g} {unit}".strip(),
        }

    async def async_set_native_value(self, value: float) -> None:
        try:
            value = int(round(float(value)))
        except (TypeError, ValueError):
            self.async_write_ha_state()
            return

        if value < self.native_min_value or value > self.native_max_value:
            # Invalid or empty UI input: do not write to the device.
            # Re-publish the entity so the number box falls back to the last valid value.
            self.async_write_ha_state()
            return

        # Alarm UI is entered in mA, Modbus register expects A.
        register_value = value if self.pre_alarm else value / 1000
        ok = await self.coordinator.write_float32_with_cooldown(
            self.slave, self._write_address, register_value
        )
        if not ok:
            raise HomeAssistantError(
                "No positive Modbus acknowledgement was received; "
                "the configuration-write outcome is unknown."
            )
        self._last_valid_value = value
        await self.coordinator.async_request_refresh()


class McbRcmThresholdNumber(SentronEntityIdMixin, CoordinatorEntity[SentronCoordinator], NumberEntity):
    """Writable 5SL6 COM MCB RCM RMS threshold configuration."""

    _attr_has_entity_name = True
    _attr_entity_category = EntityCategory.CONFIG
    _attr_mode = NumberMode.BOX
    _attr_entity_registry_enabled_default = False

    def __init__(self, coordinator: SentronCoordinator, entry: ConfigEntry, slave_info: dict, *, pre_alarm: bool) -> None:
        super().__init__(coordinator)
        self.entry = entry
        self.slave = slave_info["slave"]
        self.coordinator.register_powercenter_guarded_entity(self)
        self.pre_alarm = pre_alarm
        self._last_valid_value: int | None = None
        if pre_alarm:
            self._attr_translation_key = "rcm_rms_pre_alarm_threshold"
            self._attr_unique_id = f"{entry.entry_id}_slave_{self.slave}_rcm_rms_pre_alarm_threshold"
            self._attr_native_min_value = 50
            self._attr_native_max_value = 100
            self._attr_native_step = 1
            self._attr_native_unit_of_measurement = PERCENTAGE
            self._value_key = "rcm_rms_pre_alarm_threshold_percent"
            self._write_address = 5142  # register 5143 - offset 1
        else:
            self._attr_translation_key = "rcm_rms_alarm_threshold"
            self._attr_unique_id = f"{entry.entry_id}_slave_{self.slave}_rcm_rms_alarm_threshold"
            self._attr_native_min_value = 7
            self._attr_native_max_value = 300
            self._attr_native_step = 1
            self._attr_native_unit_of_measurement = UnitOfElectricCurrent.MILLIAMPERE
            self._value_key = "rcm_rms_alarm_threshold_a"
            self._write_address = 5144  # register 5145 - offset 1

    @property
    def slave_info(self) -> dict:
        for item in self.coordinator.data.get(SLAVES_KEY, []):
            if item["slave"] == self.slave:
                return item
        return {"slave": self.slave, "firmware": "Unknown", "name": f"{self.slave} - Unknown Device", "model": "SENTRON Unknown Device"}

    @property
    def available(self) -> bool:
        return (
            self.coordinator.is_unit_connected(self.slave)
            and not self.coordinator.should_block_powercenter_interaction(
                slave=self.slave
            )
        )

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
        value = self.coordinator.data.get(VALUES_KEY, {}).get(self.slave, {}).get(self._value_key)
        if isinstance(value, (int, float)):
            # Pre-alarm is stored/displayed as percent. Alarm threshold is stored in A,
            # but displayed in mA for consistency with ECPD.
            ui_value = int(round(float(value))) if self.pre_alarm else int(round(float(value) * 1000))
            if self.native_min_value <= ui_value <= self.native_max_value:
                self._last_valid_value = ui_value
                return ui_value
        return self._last_valid_value

    @property
    def extra_state_attributes(self) -> dict[str, float | str]:
        unit = self.native_unit_of_measurement or ""
        return {
            "allowed_min": self.native_min_value,
            "allowed_max": self.native_max_value,
            "allowed_range": f"{self.native_min_value:g}-{self.native_max_value:g} {unit}".strip(),
        }

    async def async_set_native_value(self, value: float) -> None:
        try:
            value = float(value)
        except (TypeError, ValueError):
            self.async_write_ha_state()
            return
        value = int(round(value))
        if value < self.native_min_value or value > self.native_max_value:
            self.async_write_ha_state()
            return
        # Pre-alarm register expects percent. Alarm threshold UI is mA,
        # Modbus register expects A.
        register_value = value if self.pre_alarm else value / 1000
        ok = await self.coordinator.write_float32_with_cooldown(
            self.slave, self._write_address, register_value
        )
        if not ok:
            raise HomeAssistantError(
                "No positive Modbus acknowledgement was received; "
                "the configuration-write outcome is unknown."
            )
        self._last_valid_value = value
        await self.coordinator.async_request_refresh()
