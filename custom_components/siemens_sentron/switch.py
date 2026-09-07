"""Switch platform for Siemens SENTRON."""

from __future__ import annotations

import asyncio
import logging

from homeassistant.components.switch import SwitchEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.const import EntityCategory
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import (
    DOMAIN,
    ECPD_SWITCH_VARIANTS,
    MCB_RCM_VARIANTS,
    RCA_SWITCH_VARIANTS,
    DIDO_VARIANTS,
    LOCALIZE_SWITCH_VARIANTS,
    GATEWAY_DEVICE_KEY,
    GATEWAY_SLAVE,
    MANUFACTURER,
    get_device_configuration_url,
    PAC2200_SLAVE,
    SLAVES_KEY,
    VALUES_KEY,
    RCA_HANDLE_ON_STATES,
    RCA_HANDLE_OFF_STATES,
)
from .device_types import (
    DEVICE_KIND_PAC2200,
    DEVICE_KIND_POWERCENTER,
    is_versicharge_root,
)
from .coordinator import SentronCoordinator
from .entity_ids import SentronEntityIdMixin

_LOGGER = logging.getLogger(__name__)


def _require_positive_ack(ok: bool, action: str) -> None:
    """Raise instead of presenting an unacknowledged command as successful."""
    if not ok:
        raise HomeAssistantError(
            f"{action}: no positive Modbus acknowledgement was received; "
            "the command outcome is unknown."
        )


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    coordinator: SentronCoordinator = hass.data[DOMAIN][entry.entry_id]
    entities: list[SwitchEntity] = []

    gateway = coordinator.data.get(GATEWAY_DEVICE_KEY, {})
    if gateway.get("device_kind") in (DEVICE_KIND_POWERCENTER, DEVICE_KIND_PAC2200):
        entities.append(RootDeviceLocalizeSwitchEntity(coordinator, entry))
    if is_versicharge_root(gateway):
        entities.append(VersiChargeChargingSwitchEntity(coordinator, entry))

    for slave_info in coordinator.data.get(SLAVES_KEY, []):
        if slave_info.get("variant") in LOCALIZE_SWITCH_VARIANTS:
            entities.append(DeviceLocalizeSwitchEntity(coordinator, entry, slave_info))

        if slave_info.get("variant") in ECPD_SWITCH_VARIANTS:
            entities.append(EcpdStandbySwitchEntity(coordinator, entry, slave_info))
            entities.append(EcpdUnlockSwitchEntity(coordinator, entry, slave_info))
            entities.append(EcpdRcmEnableSwitchEntity(coordinator, entry, slave_info, pre_alarm=True))
            entities.append(EcpdRcmEnableSwitchEntity(coordinator, entry, slave_info, pre_alarm=False))

        if slave_info.get("variant") in MCB_RCM_VARIANTS:
            entities.append(McbRcmEnableSwitchEntity(coordinator, entry, slave_info, pre_alarm=True))
            entities.append(McbRcmEnableSwitchEntity(coordinator, entry, slave_info, pre_alarm=False))

        if slave_info.get("variant") in RCA_SWITCH_VARIANTS:
            entities.append(RcaHandleSwitchEntity(coordinator, entry, slave_info))

        if slave_info.get("variant") in DIDO_VARIANTS:
            entities.append(DidoForceOutputSwitchEntity(coordinator, entry, slave_info, output_number=1))
            entities.append(DidoForceOutputSwitchEntity(coordinator, entry, slave_info, output_number=2))

    async_add_entities(entities)


class VersiChargeChargingSwitchEntity(
    SentronEntityIdMixin, CoordinatorEntity[SentronCoordinator], SwitchEntity
):
    """Pause or resume charging through current-limit register 1633."""

    _attr_has_entity_name = True
    _attr_translation_key = "versicharge_charging_enabled"
    _attr_icon = "mdi:ev-station"
    _attr_entity_registry_enabled_default = False

    def __init__(self, coordinator: SentronCoordinator, entry: ConfigEntry) -> None:
        super().__init__(coordinator)
        self.entry = entry
        self._attr_unique_id = f"{entry.entry_id}_versicharge_charging_enabled"

    @property
    def available(self) -> bool:
        gateway = self.coordinator.data.get(GATEWAY_DEVICE_KEY, {}) if self.coordinator.data else {}
        return (
            self.coordinator.last_update_success
            and is_versicharge_root(gateway)
            and self.coordinator.versicharge_current_control_available
        )

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
    def is_on(self) -> bool | None:
        return self.coordinator.versicharge_enabled_state

    @property
    def extra_state_attributes(self) -> dict[str, object]:
        values = self.coordinator.get_versicharge_values()
        return {
            "actual_limit_a": values.get("charging_current_limit"),
            "actual_limit_raw": values.get("charging_current_limit_raw"),
            "readback_fresh": values.get("charging_current_limit_fresh", False),
            "resume_current_a": self.coordinator.versicharge_target_current,
            "resume_power_kw": self.coordinator.versicharge_target_power_kw,
            "last_commanded_current_a": (
                self.coordinator.versicharge_last_commanded_current
            ),
            "modbus_register": 1633,
        }

    async def async_turn_on(self, **kwargs) -> None:
        await self.coordinator.async_set_versicharge_enabled(True)

    async def async_turn_off(self, **kwargs) -> None:
        await self.coordinator.async_set_versicharge_enabled(False)



class RootDeviceLocalizeSwitchEntity(SentronEntityIdMixin, CoordinatorEntity[SentronCoordinator], SwitchEntity):
    """Switch root device blinking for localization on or off.

    Powercenter gateways (1000/1100/2000) and PAC2200 are independent root
    device types and use different Modbus unit IDs:
    - Powercenter: slave 255, Siemens register offset -1, command address 96.
    - PAC2200: slave 1, PAC data dictionary command offset 65326.
    """

    _attr_has_entity_name = True
    _attr_translation_key = "locate_device"
    _attr_icon = "mdi:led-outline"
    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_entity_registry_enabled_default = True

    def __init__(self, coordinator: SentronCoordinator, entry: ConfigEntry) -> None:
        super().__init__(coordinator)
        self.entry = entry
        self._attr_unique_id = f"{entry.entry_id}_root_device_localize"
        self._attr_is_on = False
        self.coordinator.register_powercenter_guarded_entity(self)

    @property
    def available(self) -> bool:
        gateway = self.coordinator.data.get(GATEWAY_DEVICE_KEY, {}) if self.coordinator.data else {}
        if not self.coordinator.last_update_success:
            return False
        if gateway.get("device_kind") == DEVICE_KIND_POWERCENTER:
            return not self.coordinator.should_block_powercenter_interaction(slave=GATEWAY_SLAVE, command=True)
        return True

    @property
    def device_info(self) -> DeviceInfo:
        gateway = self.coordinator.data[GATEWAY_DEVICE_KEY]
        return DeviceInfo(
            identifiers={(DOMAIN, gateway["id"])},
            manufacturer=MANUFACTURER,
            model=gateway["model"],
            name=gateway["name"],
            sw_version=gateway["firmware"],
            configuration_url=get_device_configuration_url(gateway, gateway=gateway, prefer_local=True),
        )

    @property
    def is_on(self) -> bool:
        return bool(self._attr_is_on)

    def _command_target(self) -> tuple[int, int]:
        gateway = self.coordinator.data.get(GATEWAY_DEVICE_KEY, {})
        if gateway.get("device_kind") == DEVICE_KIND_PAC2200:
            return PAC2200_SLAVE, 65326
        if gateway.get("device_kind") == DEVICE_KIND_POWERCENTER:
            return GATEWAY_SLAVE, 96
        raise HomeAssistantError("Root device has no documented identify command")

    async def _write_localize(self, value: int) -> None:
        slave, address = self._command_target()
        ok = await self.coordinator.write_uint16_command_with_cooldown(
            slave=slave,
            address=address,
            value=value,
        )
        _require_positive_ack(ok, "Root-device identify command failed")

        self._attr_is_on = bool(value)
        self.async_write_ha_state()

        try:
            await asyncio.sleep(0.2)
            await self.coordinator.async_request_refresh()
        except Exception as err:  # noqa: BLE001
            _LOGGER.debug("Refresh after root device localize command ignored: %r", err)

    async def async_turn_on(self, **kwargs) -> None:
        await self._write_localize(1)

    async def async_turn_off(self, **kwargs) -> None:
        await self._write_localize(0)


class SentronBaseSwitchEntity(SentronEntityIdMixin, CoordinatorEntity[SentronCoordinator], SwitchEntity):
    """Base class for SENTRON switch entities."""

    _attr_has_entity_name = True
    _attr_entity_registry_enabled_default = False

    def __init__(self, coordinator: SentronCoordinator, entry: ConfigEntry, slave_info: dict) -> None:
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


class DeviceLocalizeSwitchEntity(SentronBaseSwitchEntity):
    """Switch end-device blinking for localization on or off."""

    _attr_translation_key = "locate_device"
    _attr_icon = "mdi:led-outline"
    _attr_entity_category = EntityCategory.DIAGNOSTIC

    def __init__(self, coordinator: SentronCoordinator, entry: ConfigEntry, slave_info: dict) -> None:
        super().__init__(coordinator, entry, slave_info)
        self._attr_unique_id = f"{entry.entry_id}_slave_{self.slave}_device_localize"
        self._attr_is_on = False

    @property
    def is_on(self) -> bool:
        return bool(self._attr_is_on)

    async def _write_localize(self, value: int) -> None:
        ok = await self.coordinator.write_uint16_command_with_cooldown(
            slave=self.slave,
            address=96,       # Map decimal 97 minus Modbus offset 1
            value=value,      # 1 = blinking on, 0 = blinking off
        )
        _require_positive_ack(ok, "Device identify command failed")

        self._attr_is_on = bool(value)
        self.async_write_ha_state()

        try:
            await asyncio.sleep(0.2)
            await self.coordinator.async_request_refresh()
        except Exception as err:  # noqa: BLE001
            _LOGGER.debug("Refresh after device localize command ignored: %r", err)

    async def async_turn_on(self, **kwargs) -> None:
        await self._write_localize(1)

    async def async_turn_off(self, **kwargs) -> None:
        await self._write_localize(0)


class EcpdStandbySwitchEntity(SentronBaseSwitchEntity):
    _attr_translation_key = "switch_standby"
    _attr_entity_registry_enabled_default = False

    _ON_STATES = {"On"}
    _STANDBY_STATES = {"Standby", "Standby (ECPD)"}
    _STANDBY_TRIP_STATES = {"Standby trip", "Standby tripped (ECPD)"}
    _OFF_STATES = {"Off", "Off trip"}
    _TRIP_STATES = {"Tripped", "On trip", "Tripped, but handle blocked"}

    def __init__(self, coordinator: SentronCoordinator, entry: ConfigEntry, slave_info: dict) -> None:
        super().__init__(coordinator, entry, slave_info)
        self._attr_unique_id = f"{entry.entry_id}_slave_{self.slave}_standby_switch"

    @property
    def _breaker_state(self) -> str | None:
        values = self.coordinator.data.get(VALUES_KEY, {})
        return values.get(self.slave, {}).get("breaker_state")

    @property
    def available(self) -> bool:
        if not super().available:
            return False

        state = self._breaker_state
        return state in (self._ON_STATES | self._STANDBY_STATES | self._STANDBY_TRIP_STATES)

    @property
    def is_on(self) -> bool | None:
        state = self._breaker_state

        if state in self._ON_STATES:
            return True
        if state in (self._STANDBY_STATES | self._STANDBY_TRIP_STATES):
            return False
        return None

    async def async_turn_on(self, **kwargs) -> None:
        state = self._breaker_state

        if self.coordinator.is_ecpd_standby_cooldown_active(self.slave):
            remaining = self.coordinator.get_ecpd_standby_cooldown_remaining(self.slave)
            raise HomeAssistantError(f"ECPD verarbeitet noch. Bitte {remaining} s warten.")

        if state in self._OFF_STATES:
            raise HomeAssistantError("Aus-Zustände können nicht elektronisch eingeschaltet werden.")

        if state in self._TRIP_STATES:
            raise HomeAssistantError("Direktes Einschalten aus Trip-Zustand ist nicht erlaubt.")

        if state not in self._STANDBY_STATES:
            raise HomeAssistantError(f"Aktueller Schalterzustand erlaubt kein Einschalten: {state}")

        ok = await self.coordinator.write_uint16_command_with_cooldown(
            slave=self.slave,
            address=3692,       # Electronic switching: register 3693 minus Modbus offset 1
            value=1,            # Map: 0 = STANDBY, 1 = ON
        )
        _require_positive_ack(ok, "ECPD ON command failed")

        try:
            await asyncio.sleep(0.2)
            await self.coordinator.async_request_refresh()
        except Exception as err:  # noqa: BLE001
            _LOGGER.debug("ECPD refresh after Einschalten ignored: %r", err)

    async def async_turn_off(self, **kwargs) -> None:
        state = self._breaker_state

        if self.coordinator.is_ecpd_standby_cooldown_active(self.slave):
            remaining = self.coordinator.get_ecpd_standby_cooldown_remaining(self.slave)
            raise HomeAssistantError(f"ECPD verarbeitet noch. Bitte {remaining} s warten.")

        if state in self._OFF_STATES:
            raise HomeAssistantError("Aus-Zustände können nicht elektronisch geschaltet werden.")

        if state not in (self._ON_STATES | self._STANDBY_STATES | self._STANDBY_TRIP_STATES):
            raise HomeAssistantError(f"Aktueller Schalterzustand erlaubt kein Schalten auf Standby: {state}")

        ok = await self.coordinator.write_uint16_command_with_cooldown(
            slave=self.slave,
            address=3692,       # Electronic switching: register 3693 minus Modbus offset 1
            value=0,            # Map: 0 = STANDBY, 1 = ON
        )
        _require_positive_ack(ok, "ECPD standby command failed")

        try:
            await asyncio.sleep(0.2)
            await self.coordinator.async_request_refresh()
        except Exception as err:  # noqa: BLE001
            _LOGGER.debug("ECPD refresh after Standby ignored: %r", err)


class EcpdUnlockSwitchEntity(SentronBaseSwitchEntity):
    """Unlock protected ECPD parameters via local acknowledge flow."""

    _attr_translation_key = "unlock"
    _attr_entity_category = EntityCategory.CONFIG
    _attr_entity_registry_enabled_default = False

    def __init__(self, coordinator: SentronCoordinator, entry: ConfigEntry, slave_info: dict) -> None:
        super().__init__(coordinator, entry, slave_info)
        self._attr_unique_id = f"{entry.entry_id}_slave_{self.slave}_unlock"

    @property
    def available(self) -> bool:
        return (
            self.coordinator.is_unit_connected(self.slave)
            and not self.coordinator.should_block_powercenter_interaction(
                slave=self.slave, command=True
            )
        )

    @property
    def _unlock_status_raw(self) -> int | None:
        value = self.coordinator.data.get(VALUES_KEY, {}).get(self.slave, {}).get("unlock_status")
        return value if isinstance(value, int) else None

    @property
    def is_on(self) -> bool | None:
        status = self._unlock_status_raw
        if status is None:
            return None
        if status == 0:
            return False
        if status == 2 and not self.coordinator.is_ecpd_unlock_ack_active(self.slave):
            return False
        return status in (1, 2, 3)

    @property
    def icon(self) -> str:
        status = self._unlock_status_raw
        if status in (1, 3):
            return "mdi:lock-open-variant-outline"
        return "mdi:lock-outline"

    async def _write_unlock_command(self, value: int) -> None:
        ok = await self.coordinator.write_uint16_command_with_cooldown(
            slave=self.slave,
            address=3694,      # Register 3695 minus Modbus offset 1 on the ECPD slave device
            value=value,       # 0 = unlock request, 1 = lock request
        )
        _require_positive_ack(ok, "ECPD lock/unlock command failed")

        if value == 0:
            self.coordinator.start_ecpd_unlock_ack(self.slave)
        else:
            self.coordinator.reset_ecpd_unlock_ack(self.slave)

        try:
            await asyncio.sleep(0.2)
            await self.coordinator.async_request_refresh()
        except Exception as err:  # noqa: BLE001
            _LOGGER.debug("ECPD refresh after unlock command ignored: %r", err)

    async def async_turn_on(self, **kwargs) -> None:
        await self._write_unlock_command(0)

    async def async_turn_off(self, **kwargs) -> None:
        await self._write_unlock_command(1)

class DidoForceOutputSwitchEntity(SentronBaseSwitchEntity):
    """Force a DIDO output via command register."""

    _attr_entity_registry_enabled_default = False
    _attr_icon = "mdi:electric-switch"

    def __init__(self, coordinator: SentronCoordinator, entry: ConfigEntry, slave_info: dict, *, output_number: int) -> None:
        super().__init__(coordinator, entry, slave_info)
        self.output_number = output_number
        self._attr_translation_key = f"output_force_{output_number}"
        self._attr_unique_id = f"{entry.entry_id}_slave_{self.slave}_force_output_{output_number}"

    @property
    def _forcing_state(self) -> dict | None:
        values = self.coordinator.data.get(VALUES_KEY, {})
        return values.get(self.slave, {}).get(f"output_{self.output_number}_forcing")

    @property
    def is_on(self) -> bool | None:
        state = self._forcing_state
        if not isinstance(state, dict):
            return None
        return bool(state.get("output_state"))

    async def _write_force_command(self, state: int, seconds: int) -> None:
        # Modbus map: decimal 3698, U8 output number / U8 state / U16 force time; offset -1.
        ok = await self.coordinator.write_u8_u8_u16_command_with_cooldown(
            slave=self.slave,
            address=3697,
            first_u8=self.output_number,
            second_u8=state,
            value_u16=seconds,
        )
        _require_positive_ack(ok, "DIDO force-output command failed")

        try:
            await asyncio.sleep(0.4)
            await self.coordinator.async_request_refresh()
        except Exception as err:  # noqa: BLE001
            _LOGGER.debug("DIDO refresh after force command ignored: %r", err)

    async def async_turn_on(self, **kwargs) -> None:
        await self._write_force_command(state=1, seconds=3600)

    async def async_turn_off(self, **kwargs) -> None:
        await self._write_force_command(state=0, seconds=1)


class EcpdRcmEnableSwitchEntity(SentronBaseSwitchEntity):
    """Enable/disable ECPD RCM AC pre-alarm/alarm."""

    _attr_entity_category = EntityCategory.CONFIG
    _attr_entity_registry_enabled_default = False

    def __init__(self, coordinator: SentronCoordinator, entry: ConfigEntry, slave_info: dict, *, pre_alarm: bool) -> None:
        super().__init__(coordinator, entry, slave_info)
        self.pre_alarm = pre_alarm
        if pre_alarm:
            self._attr_translation_key = "rcm_ac_pre_alarm_enable"
            self._attr_unique_id = f"{entry.entry_id}_slave_{self.slave}_rcm_ac_pre_alarm_enable"
            self._value_key = "rcm_ac_pre_alarm_enabled"
            self._address = 5134  # register 5135 - offset 1
        else:
            self._attr_translation_key = "rcm_ac_alarm_enable"
            self._attr_unique_id = f"{entry.entry_id}_slave_{self.slave}_rcm_ac_alarm_enable"
            self._value_key = "rcm_ac_alarm_enabled"
            self._address = 5135  # register 5136 - offset 1

    @property
    def is_on(self) -> bool | None:
        value = self.coordinator.data.get(VALUES_KEY, {}).get(self.slave, {}).get(self._value_key)
        if value is None:
            return None
        return bool(value)

    async def _write_enabled(self, enabled: bool) -> None:
        ok = await self.coordinator.write_uint16_with_cooldown(
            self.slave, self._address, 1 if enabled else 0
        )
        _require_positive_ack(ok, "ECPD RCM configuration write failed")
        await self.coordinator.async_request_refresh()

    async def async_turn_on(self, **kwargs) -> None:
        await self._write_enabled(True)

    async def async_turn_off(self, **kwargs) -> None:
        await self._write_enabled(False)



class McbRcmEnableSwitchEntity(SentronBaseSwitchEntity):
    """Enable/disable 5SL6 COM MCB RCM RMS pre-alarm/alarm."""

    _attr_entity_category = EntityCategory.CONFIG
    _attr_entity_registry_enabled_default = False

    def __init__(self, coordinator: SentronCoordinator, entry: ConfigEntry, slave_info: dict, *, pre_alarm: bool) -> None:
        super().__init__(coordinator, entry, slave_info)
        self.pre_alarm = pre_alarm
        if pre_alarm:
            self._attr_translation_key = "rcm_rms_pre_alarm_enable"
            self._attr_unique_id = f"{entry.entry_id}_slave_{self.slave}_rcm_rms_pre_alarm_enable"
            self._value_key = "rcm_rms_pre_alarm_enabled"
            self._address = 5140  # register 5141 - offset 1
        else:
            self._attr_translation_key = "rcm_rms_alarm_enable"
            self._attr_unique_id = f"{entry.entry_id}_slave_{self.slave}_rcm_rms_alarm_enable"
            self._value_key = "rcm_rms_alarm_enabled"
            self._address = 5141  # register 5142 - offset 1

    @property
    def is_on(self) -> bool | None:
        value = self.coordinator.data.get(VALUES_KEY, {}).get(self.slave, {}).get(self._value_key)
        if value is None:
            return None
        return bool(value)

    async def _write_enabled(self, enabled: bool) -> None:
        ok = await self.coordinator.write_uint16_with_cooldown(
            self.slave, self._address, 1 if enabled else 0
        )
        _require_positive_ack(ok, "MCB RCM configuration write failed")
        await self.coordinator.async_request_refresh()

    async def async_turn_on(self, **kwargs) -> None:
        await self._write_enabled(True)

    async def async_turn_off(self, **kwargs) -> None:
        await self._write_enabled(False)
class RcaHandleSwitchEntity(SentronBaseSwitchEntity):
    """Remote handle ON/OFF command for 5ST3 COM RCA."""

    _attr_translation_key = "rca_handle"
    _attr_entity_registry_enabled_default = False

    def __init__(self, coordinator: SentronCoordinator, entry: ConfigEntry, slave_info: dict) -> None:
        super().__init__(coordinator, entry, slave_info)
        self._attr_unique_id = f"{entry.entry_id}_slave_{self.slave}_rca_handle"

    @property
    def _handle_state_raw(self) -> int | None:
        return self.coordinator.data.get(VALUES_KEY, {}).get(self.slave, {}).get("rca_handle_state_raw")

    @property
    def available(self) -> bool:
        if not self.coordinator.is_unit_connected(self.slave):
            return False
        if self.coordinator.should_block_powercenter_interaction(slave=self.slave, command=True):
            return False
        values = self.coordinator.data.get(VALUES_KEY, {}).get(self.slave, {})
        return values.get("remote_control_selector") == 1

    @property
    def is_on(self) -> bool | None:
        state = self._handle_state_raw
        if state in RCA_HANDLE_ON_STATES:
            return True
        if state in RCA_HANDLE_OFF_STATES:
            return False
        return None

    async def _write_handle(self, value: int) -> None:
        values = self.coordinator.data.get(VALUES_KEY, {}).get(self.slave, {})
        if values.get("remote_control_selector") != 1:
            raise HomeAssistantError("Remote Control Selector ist nicht auf Kommunikation gesetzt.")
        ok = await self.coordinator.write_uint16_command_with_cooldown(
            slave=self.slave,
            address=3688,
            value=value,
        )
        _require_positive_ack(ok, "RCA handle command failed")
        await asyncio.sleep(1.0)
        await self.coordinator.async_request_refresh()

    async def async_turn_on(self, **kwargs) -> None:
        await self._write_handle(1)

    async def async_turn_off(self, **kwargs) -> None:
        await self._write_handle(0)
