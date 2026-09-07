"""Button platform for Siemens SENTRON."""

from __future__ import annotations

import asyncio

from homeassistant.components.button import ButtonEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import (
    DOMAIN,
    ECPD_SWITCH_VARIANTS,
    RCA_SWITCH_VARIANTS,
    RCM_TEST_VARIANTS,
    GATEWAY_DEVICE_KEY,
    MANUFACTURER,
    get_device_configuration_url,
    SLAVES_KEY,
)
from .coordinator import SentronCoordinator
from .entity_ids import SentronEntityIdMixin

async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    coordinator: SentronCoordinator = hass.data[DOMAIN][entry.entry_id]
    entities: list[ButtonEntity] = []

    for slave_info in coordinator.data.get(SLAVES_KEY, []):
        if slave_info.get("variant") in ECPD_SWITCH_VARIANTS:
            entities.append(EcpdDeviceTestButtonEntity(coordinator, entry, slave_info))
            entities.append(EcpdHardwareDisconnectButtonEntity(coordinator, entry, slave_info))

        if slave_info.get("variant") in RCA_SWITCH_VARIANTS:
            entities.append(RcaResetManualOffButtonEntity(coordinator, entry, slave_info))

        if slave_info.get("variant") in RCM_TEST_VARIANTS:
            entities.append(RcmDeviceTestButtonEntity(coordinator, entry, slave_info))

    async_add_entities(entities)


class EcpdBaseButtonEntity(SentronEntityIdMixin, CoordinatorEntity[SentronCoordinator], ButtonEntity):
    """Base class for ECPD button entities."""

    _attr_has_entity_name = True
    _attr_entity_registry_enabled_default = False

    def __init__(
        self,
        coordinator: SentronCoordinator,
        entry: ConfigEntry,
        slave_info: dict,
    ) -> None:
        super().__init__(coordinator)
        self.entry = entry
        self.slave = slave_info["slave"]
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
    def available(self) -> bool:
        return (
            self.coordinator.is_unit_connected(self.slave)
            and not self.coordinator.should_block_powercenter_interaction(
                slave=self.slave, command=True
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

    async def _write_and_refresh(self, address: int, value: int, error_text: str) -> None:
        ok = await self.coordinator.write_uint16_command_with_cooldown(
            slave=self.slave,
            address=address,
            value=value,
        )
        if not ok:
            raise HomeAssistantError(
                f"{error_text} No positive Modbus acknowledgement was received; "
                "the command outcome is unknown."
            )

        await asyncio.sleep(0.7)
        await self.coordinator.async_request_refresh()


class EcpdDeviceTestButtonEntity(EcpdBaseButtonEntity):
    """Start device test for ECPD."""

    _attr_translation_key = "start_self_rcd_test"
    _attr_icon = "mdi:clipboard-pulse-outline"

    def __init__(self, coordinator: SentronCoordinator, entry: ConfigEntry, slave_info: dict) -> None:
        super().__init__(coordinator, entry, slave_info)
        self._attr_unique_id = f"{entry.entry_id}_slave_{self.slave}_device_test"

    @property
    def available(self) -> bool:
        return super().available

    async def async_press(self) -> None:
        if self.coordinator.is_ecpd_standby_cooldown_active(self.slave):
            remaining = self.coordinator.get_ecpd_standby_cooldown_remaining(self.slave)
            raise HomeAssistantError(f"ECPD verarbeitet noch. Bitte {remaining} s warten.")

        self.coordinator.start_ecpd_device_test_tracking(self.slave)
        try:
            await self._write_and_refresh(
                address=2677,       # Map decimal 2678 minus Modbus offset 1
                value=0x0815,
                error_text="ECPD test write failed.",
            )
        except Exception:
            self.coordinator.cancel_device_test_tracking(self.slave, "ecpd")
            raise


class RcmDeviceTestButtonEntity(EcpdBaseButtonEntity):
    """Start RCM test for 5SL6 COM MCB RCM."""

    _attr_translation_key = "start_rcm_test"
    _attr_icon = "mdi:clipboard-pulse-outline"

    def __init__(self, coordinator: SentronCoordinator, entry: ConfigEntry, slave_info: dict) -> None:
        super().__init__(coordinator, entry, slave_info)
        self._attr_unique_id = f"{entry.entry_id}_slave_{self.slave}_rcm_test"

    async def async_press(self) -> None:
        self.coordinator.start_device_test_tracking(
            self.slave,
            kind="rcm",
            status_key="rcm_test_status",
            timestamp_key="rcm_test_timestamp",
        )
        try:
            await self._write_and_refresh(
                address=5225,       # Map decimal 5226 minus Modbus offset 1
                value=0x0815,
                error_text="RCM test write failed.",
            )
        except Exception:
            self.coordinator.cancel_device_test_tracking(self.slave, "rcm")
            raise


class EcpdHardwareDisconnectButtonEntity(EcpdBaseButtonEntity):
    """Hardware disconnect for ECPD."""

    _attr_translation_key = "unpair_device"
    _attr_icon = "mdi:electric-switch"
    _attr_entity_category = EntityCategory.CONFIG
    _attr_entity_registry_enabled_default = False

    def __init__(self, coordinator: SentronCoordinator, entry: ConfigEntry, slave_info: dict) -> None:
        super().__init__(coordinator, entry, slave_info)
        self._attr_unique_id = f"{entry.entry_id}_slave_{self.slave}_hardware_disconnect"

    @property
    def available(self) -> bool:
        return super().available

    async def async_press(self) -> None:
        if self.coordinator.is_ecpd_standby_cooldown_active(self.slave):
            remaining = self.coordinator.get_ecpd_standby_cooldown_remaining(self.slave)
            raise HomeAssistantError(f"ECPD verarbeitet noch. Bitte {remaining} s warten.")

        await self._write_and_refresh(
            address=3693,       # Map decimal 3694 minus Modbus offset 1
            value=0x0815,
            error_text="Unumkehrlich trennen Schreibvorgang fehlgeschlagen.",
        )


class RcaResetManualOffButtonEntity(EcpdBaseButtonEntity):
    """Reset Manual Off for 5ST3 COM RCA."""

    _attr_translation_key = "reset_manual_off"
    _attr_icon = "mdi:restore"

    def __init__(self, coordinator: SentronCoordinator, entry: ConfigEntry, slave_info: dict) -> None:
        super().__init__(coordinator, entry, slave_info)
        self._attr_unique_id = f"{entry.entry_id}_slave_{self.slave}_reset_manual_off"

    async def async_press(self) -> None:
        await self._write_and_refresh(
            address=3689,       # Reset Manual Off: register 3690 minus Modbus offset 1
            value=0x0815,
            error_text="Reset Manual Off Schreibvorgang fehlgeschlagen.",
        )
