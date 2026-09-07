"""Select platform for Siemens SENTRON."""

from __future__ import annotations

import asyncio

from homeassistant.components.select import SelectEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import (
    ARD_AUTO_RECLOSE_OPTIONS,
    ATTACHED_DEVICE_TYPE_OPTIONS,
    DOMAIN,
    ECPD_CONFIG_VARIANTS,
    ECPD_NOMINAL_CURRENT_OPTIONS,
    ECPD_RCD_SENSITIVITY_OPTIONS,
    ECPD_RCD_TRIPPING_TIME_OPTIONS,
    ECPD_TRIP_BEHAVIOUR_OPTIONS,
    GATEWAY_DEVICE_KEY,
    MANUFACTURER,
    get_device_configuration_url,
    RCA_CONFIG_VARIANTS,
    RCA_SWITCH_VARIANTS,
    REMOTE_CONTROL_SELECTOR_OPTIONS,
    SLAVES_KEY,
    VALUES_KEY,
)
from .coordinator import SentronCoordinator
from .entity_ids import SentronEntityIdMixin


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up SENTRON select entities."""
    coordinator: SentronCoordinator = hass.data[DOMAIN][entry.entry_id]
    entities: list[SelectEntity] = []

    for slave_info in coordinator.data.get(SLAVES_KEY, []):
        variant = slave_info.get("variant")
        if variant in RCA_CONFIG_VARIANTS:
            entities.append(AttachedDeviceTypeSelectEntity(coordinator, entry, slave_info))
        if variant in RCA_SWITCH_VARIANTS:
            entities.append(RcaArdAutoRecloseSelectEntity(coordinator, entry, slave_info))
            entities.append(RcaRemoteControlSelectEntity(coordinator, entry, slave_info))
        if variant in ECPD_CONFIG_VARIANTS:
            entities.extend((
                EcpdProtectedConfigSelectEntity(coordinator, entry, slave_info, key="ecpd_nominal_current", name="Nominal Current", translation_key="ecpd_nominal_current", icon="mdi:current-ac", options_map=ECPD_NOMINAL_CURRENT_OPTIONS, address=5375),
                EcpdProtectedConfigSelectEntity(coordinator, entry, slave_info, key="ecpd_instantaneous_trip_behaviour", name="Instantaneous Trip Behaviour", translation_key="ecpd_instantaneous_trip_behaviour", icon="mdi:shield-alert-outline", options_map=ECPD_TRIP_BEHAVIOUR_OPTIONS, address=5379),
                EcpdProtectedConfigSelectEntity(coordinator, entry, slave_info, key="ecpd_time_delay_release_behaviour", name="Time-Delay Release Behaviour", translation_key="ecpd_time_delay_release_behaviour", icon="mdi:shield-alert-outline", options_map=ECPD_TRIP_BEHAVIOUR_OPTIONS, address=5380),
                EcpdProtectedConfigSelectEntity(coordinator, entry, slave_info, key="ecpd_rcd_sensitivity", name="RCD Sensitivity", translation_key="ecpd_rcd_sensitivity", icon="mdi:tune-vertical", options_map=ECPD_RCD_SENSITIVITY_OPTIONS, address=5382),
                EcpdProtectedConfigSelectEntity(coordinator, entry, slave_info, key="ecpd_rcd_tripping_time", name="RCD Tripping Time", translation_key="ecpd_rcd_tripping_time", icon="mdi:timer-cog-outline", options_map=ECPD_RCD_TRIPPING_TIME_OPTIONS, address=5383),
                EcpdProtectedConfigSelectEntity(coordinator, entry, slave_info, key="ecpd_residual_current_trip_behaviour", name="Residual-Current Trip Behaviour", translation_key="ecpd_residual_current_trip_behaviour", icon="mdi:shield-alert-outline", options_map=ECPD_TRIP_BEHAVIOUR_OPTIONS, address=5384),
            ))

    async_add_entities(entities)


class SentronBaseSelectEntity(SentronEntityIdMixin, CoordinatorEntity[SentronCoordinator], SelectEntity):
    """Base class for SENTRON select entities."""

    _attr_has_entity_name = True
    _attr_entity_category = EntityCategory.CONFIG
    _attr_entity_registry_enabled_default = False

    def __init__(self, coordinator: SentronCoordinator, entry: ConfigEntry, slave_info: dict) -> None:
        super().__init__(coordinator)
        self.entry = entry
        self.slave = slave_info["slave"]
        self._last_raw: int | None = None
        self.coordinator.register_powercenter_guarded_entity(self)

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
    def available(self) -> bool:
        """Keep the last verified value visible during a write cooldown.

        Home Assistant has no separate dynamic "disabled but keep current value"
        state for SelectEntity. Returning False here renders the entity state as
        unavailable. Powercenter 1000 can temporarily miss direct slave read-back
        values during/after delayed-ACK cooldown, so using availability as the UI
        lock makes the select stick at unavailable.

        The actual cooldown protection is implemented in async_select_option()
        and the coordinator write path. A disconnected unit is unavailable.
        """
        return self.coordinator.is_unit_connected(self.slave)

    @property
    def extra_state_attributes(self) -> dict[str, object]:
        remaining = self.coordinator.get_powercenter_write_cooldown_remaining()
        return {
            "powercenter_cooldown_active": remaining > 0,
            "powercenter_cooldown_remaining_s": remaining,
            "write_blocked_by_cooldown": self.coordinator.should_block_powercenter_interaction(slave=self.slave),
        }

    @property
    def options(self) -> list[str]:
        return list(self._options_map.values())

    @property
    def current_option(self) -> str | None:
        raw = self.coordinator.data.get(VALUES_KEY, {}).get(self.slave, {}).get(self._value_key)

        # Powercenter 1000 can temporarily return None for configuration values
        # after cooldown/unlock, while discovery metadata still contains the
        # configured value. Avoid rendering the select as unavailable.
        if raw is None and self._value_key == "attached_device_type":
            raw = self.slave_info.get("attached_device_type")
        if raw is None:
            raw = self._last_raw
        if raw is None:
            return None

        try:
            raw_int = int(raw)
        except (TypeError, ValueError):
            return None

        self._last_raw = raw_int
        return self._options_map.get(raw_int, f"Unknown ({raw_int})")

    async def async_select_option(self, option: str) -> None:
        reverse = {label: value for value, label in self._options_map.items()}
        if option not in reverse:
            raise HomeAssistantError(f"Unsupported option: {option}")

        raw_value = reverse[option]

        if self.coordinator.should_block_powercenter_interaction(slave=self.slave):
            remaining = self.coordinator.get_powercenter_write_cooldown_remaining()
            self.async_write_ha_state()
            raise HomeAssistantError(
                f"Powercenter verarbeitet noch. Bitte {remaining} s warten."
            )

        # Some SENTRON 5ST3 parameter writes are applied by the device/gateway but
        # still return a Modbus error/exception response. Treat the subsequent
        # read-back value as the source of truth to avoid false HA service errors.
        ok = await self.coordinator.write_uint16_command_with_cooldown(self.slave, self._address, raw_value)

        await asyncio.sleep(2.0)
        readback = await self.coordinator.modbus.read_holding_u16(self.slave, self._address)
        await self.coordinator.async_request_refresh()

        if readback == raw_value:
            self._last_raw = raw_value
            self.async_write_ha_state()
            return

        values = self.coordinator.data.get(VALUES_KEY, {}).get(self.slave, {}) if self.coordinator.data else {}
        refreshed_value = values.get(self._value_key)
        if refreshed_value == raw_value:
            self._last_raw = raw_value
            self.async_write_ha_state()
            return

        self.async_write_ha_state()
        if not ok:
            raise HomeAssistantError(
                f"Modbus write could not be verified for {self._attr_translation_key} at register {self._address + 1} / address {self._address}"
            )
        raise HomeAssistantError(
            f"Modbus write verification failed for {self._attr_translation_key} at register {self._address + 1} / address {self._address}"
        )


class AttachedDeviceTypeSelectEntity(SentronBaseSelectEntity):
    """Configured attached device type for 5ST3 COM devices."""

    _attr_translation_key = "attached_device_type"
    _attr_icon = "mdi:devices"
    _options_map = ATTACHED_DEVICE_TYPE_OPTIONS
    _value_key = "attached_device_type"
    _address = 110

    def __init__(self, coordinator: SentronCoordinator, entry: ConfigEntry, slave_info: dict) -> None:
        super().__init__(coordinator, entry, slave_info)
        self._attr_unique_id = f"{entry.entry_id}_slave_{self.slave}_attached_device_type_select"


class RcaArdAutoRecloseSelectEntity(SentronBaseSelectEntity):
    """ARD automatic reclosing configuration for 5ST3 COM RCA."""

    _attr_translation_key = "ard_auto_reclose"
    _attr_icon = "mdi:autorenew"
    _options_map = ARD_AUTO_RECLOSE_OPTIONS
    _value_key = "ard_enabled"
    _address = 3680

    def __init__(self, coordinator: SentronCoordinator, entry: ConfigEntry, slave_info: dict) -> None:
        super().__init__(coordinator, entry, slave_info)
        self._attr_unique_id = f"{entry.entry_id}_slave_{self.slave}_ard_auto_reclose_select"


class RcaRemoteControlSelectEntity(SentronBaseSelectEntity):
    """Remote control source selector for 5ST3 COM RCA."""

    _attr_translation_key = "remote_control_communication"
    _attr_icon = "mdi:remote"
    _options_map = REMOTE_CONTROL_SELECTOR_OPTIONS
    _value_key = "remote_control_selector"
    _address = 3690

    def __init__(self, coordinator: SentronCoordinator, entry: ConfigEntry, slave_info: dict) -> None:
        super().__init__(coordinator, entry, slave_info)
        self._attr_unique_id = f"{entry.entry_id}_slave_{self.slave}_remote_control_communication_select"


class EcpdProtectedConfigSelectEntity(SentronBaseSelectEntity):
    """Protected ECPD configuration select.

    The entity is only writable/available while the device reports unlocked
    state or the Siemens "time almost expired" state. The coordinator write
    helper still applies the Powercenter delayed-ACK cooldown for every write.
    """

    def __init__(
        self,
        coordinator: SentronCoordinator,
        entry: ConfigEntry,
        slave_info: dict,
        *,
        key: str,
        name: str,
        translation_key: str,
        icon: str,
        options_map: dict[int, str],
        address: int,
    ) -> None:
        super().__init__(coordinator, entry, slave_info)
        self._value_key = key
        self._attr_translation_key = translation_key
        self._attr_icon = icon
        self._options_map = options_map
        self._address = address
        self._attr_unique_id = f"{entry.entry_id}_slave_{self.slave}_{key}_select"

    def _is_protected_write_unlocked(self) -> bool:
        unlock_status = self.coordinator.data.get(VALUES_KEY, {}).get(self.slave, {}).get("unlock_status")
        return unlock_status in (1, 3)

    @property
    def available(self) -> bool:
        return (
            super().available
            and self._is_protected_write_unlocked()
            and not self.coordinator.should_block_powercenter_interaction(
                slave=self.slave
            )
        )

    @property
    def extra_state_attributes(self) -> dict[str, object]:
        attrs = super().extra_state_attributes
        unlock_status = self.coordinator.data.get(VALUES_KEY, {}).get(self.slave, {}).get("unlock_status")
        attrs.update(
            {
                "protected_parameter": True,
                "unlock_status_raw": unlock_status,
                "write_enabled_by_unlock": unlock_status in (1, 3),
            }
        )
        return attrs

    async def async_select_option(self, option: str) -> None:
        if not self._is_protected_write_unlocked():
            self.async_write_ha_state()
            raise HomeAssistantError("Geschützter Parameter ist gesperrt. Bitte ECPD Unlock durchführen und am Gerät bestätigen.")

        reverse = {label: value for value, label in self._options_map.items()}
        if option not in reverse:
            raise HomeAssistantError(f"Unsupported option: {option}")

        raw_value = reverse[option]

        if self.coordinator.should_block_powercenter_interaction(slave=self.slave):
            remaining = self.coordinator.get_powercenter_write_cooldown_remaining()
            self.async_write_ha_state()
            raise HomeAssistantError(f"Powercenter verarbeitet noch. Bitte {remaining} s warten.")

        ok = await self.coordinator.write_uint16_with_cooldown(self.slave, self._address, raw_value)

        await asyncio.sleep(2.0)
        readback = await self.coordinator.modbus.read_holding_u16(self.slave, self._address)
        await self.coordinator.async_request_refresh()

        if readback == raw_value:
            self._last_raw = raw_value
            self.async_write_ha_state()
            return

        values = self.coordinator.data.get(VALUES_KEY, {}).get(self.slave, {}) if self.coordinator.data else {}
        refreshed_value = values.get(self._value_key)
        if refreshed_value == raw_value:
            self._last_raw = raw_value
            self.async_write_ha_state()
            return

        self.async_write_ha_state()
        if not ok:
            raise HomeAssistantError(
                f"Modbus write could not be verified for {self._attr_translation_key} at register {self._address + 1} / address {self._address}"
            )
        raise HomeAssistantError(
            f"Modbus write verification failed for {self._attr_translation_key} at register {self._address + 1} / address {self._address}"
        )
