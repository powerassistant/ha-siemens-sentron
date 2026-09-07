"""Coordinator for Siemens SENTRON."""

from __future__ import annotations

import asyncio
import logging
import math
import time
import weakref
from datetime import datetime, timedelta, timezone

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, CONF_PORT
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady, HomeAssistantError
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import (
    ALARM_STATE_MAP,
    BREAKER_STATE_MAP,
    RCA_HANDLE_STATE_MAP,
    CONNECTION_STATE_MAP,
    DEVICE_STATE_MAP,
    DOMAIN,
    ECPD_STANDBY_COOLDOWN_SECONDS,
    ECPD_UNLOCK_ACK_SECONDS,
    RCA_SWITCH_VARIANTS,
    RCA_CONFIG_VARIANTS,
    MCB_RCM_VARIANTS,
    GATEWAY_DEVICE_KEY,
    GATEWAY_POC1000_CONNECTION_STATE_BASE,
    GATEWAY_POC1100_BREAKER_STATE_BASE,
    GATEWAY_POC1100_CONNECTION_STATE_BASE,
    GATEWAY_SLAVE,
    GATEWAY_STARTUP_DELAY,
    SLAVES_KEY,
    VALUES_KEY,
)
from .device_types import (
    DEVICE_KIND_POWERCENTER,
    DEVICE_KIND_VERSICHARGE,
    is_pac2200_root,
    is_powercenter_1100_or_2000,
    is_powercenter_root,
    is_versicharge_root,
)
from .discovery import async_discover_slaves
from .gateway import async_build_gateway_data
from .profiles import get_effective_device_profile
from .pac2200 import PAC2200_SENSORS, PAC2200_SLAVE_ID
from .modbus_api import SentronModbusApi
from .versicharge import (
    TotalEnergyFilter,
    VERSICHARGE_COMMAND_INTERVAL_SECONDS,
    VERSICHARGE_COMMAND_TIMEOUT_SECONDS,
    VERSICHARGE_CURRENT_REGISTER,
    VERSICHARGE_FALLBACK_CURRENT_REGISTER,
    VERSICHARGE_MAX_CURRENT,
    VERSICHARGE_MIN_CURRENT,
    VERSICHARGE_MODBUS_TIMEOUT_SECONDS,
    VERSICHARGE_POLL_INTERVAL_SECONDS,
    VERSICHARGE_STATIC_VALUE_KEYS,
    async_read_versicharge_values,
    encode_charging_current,
    nominal_power_bounds_kw,
    nominal_power_kw_for_current,
    normalize_charging_current_readback,
    power_for_current,
    quantize_power_kw,
    whole_amp_current_for_power_kw,
)

_LOGGER = logging.getLogger(__name__)

# A complete refresh consists of many serial Modbus requests.  One-second
# polling continuously saturates a Powercenter, especially when discovery is
# included.  Dynamic values remain responsive at fifteen seconds while immutable
# root metadata and the device topology are refreshed much less frequently.
_POLL_INTERVAL_SECONDS = 15
_DISCOVERY_INTERVAL_SECONDS = 300


class SentronCoordinator(DataUpdateCoordinator[dict]):
    """Handle Siemens SENTRON data updates and device discovery."""

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        self.entry = entry
        self.host: str = entry.data[CONF_HOST]
        self.port: int = entry.data[CONF_PORT]
        self.name: str = entry.title or "SENTRON Powercenter"
        modbus_timeout = (
            VERSICHARGE_MODBUS_TIMEOUT_SECONDS
            if entry.data.get("device_kind") == DEVICE_KIND_VERSICHARGE
            else 15
        )
        self.modbus = SentronModbusApi(
            self.host, self.port, timeout=modbus_timeout
        )
        self.gateway_device_registry_id: str | None = None
        self._write_lock = asyncio.Lock()
        self._root_gateway: dict | None = None
        self._cached_slaves: list[dict] = []
        self._next_discovery_at = 0.0
        self._topology_reload_task: asyncio.Task | None = None
        self._ecpd_standby_cooldown_remaining: dict[int, int] = {}
        self._ecpd_standby_cooldown_tasks: dict[int, asyncio.Task] = {}
        self._ecpd_unlock_ack_until: dict[int, float] = {}
        self._ecpd_unlock_ack_tasks: dict[int, asyncio.Task] = {}
        self._powercenter_write_cooldown_until: float = 0.0
        self._powercenter_write_cooldown_task: asyncio.Task | None = None
        self._powercenter_guarded_entities: weakref.WeakSet = weakref.WeakSet()
        self._test_running: dict[tuple[int, str], bool] = {}
        self._test_baseline: dict[tuple[int, str], tuple[object, object]] = {}
        self._test_timeout_tasks: dict[tuple[int, str], asyncio.Task] = {}
        self._test_display_cache: dict[tuple[int, str], tuple[object, object]] = {}
        self._test_started_at: dict[tuple[int, str], datetime] = {}
        self._versicharge_energy_filter = TotalEnergyFilter()
        self._versicharge_target_power_kw: float | None = None
        self._versicharge_effective_phase_count: int | None = None
        self._versicharge_command_in_progress = False
        self._versicharge_last_command_started = float("-inf")
        self._versicharge_last_local_target_update = float("-inf")
        self._versicharge_last_commanded_current: int | None = None

        poll_interval = (
            VERSICHARGE_POLL_INTERVAL_SECONDS
            if entry.data.get("device_kind") == DEVICE_KIND_VERSICHARGE
            else _POLL_INTERVAL_SECONDS
        )

        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=timedelta(seconds=poll_interval),
        )

    def _versicharge_gateway(self) -> dict:
        """Return the validated VersiCharge root or raise a service error."""
        gateway = self.data.get(GATEWAY_DEVICE_KEY, {}) if self.data else {}
        if not is_versicharge_root(gateway):
            raise HomeAssistantError("This config entry is not a VersiCharge")
        return gateway

    def get_versicharge_values(self) -> dict:
        """Return the latest decoded values for the root charger."""
        gateway = self._versicharge_gateway()
        unit_id = int(gateway["unit_id"])
        return self.data.get(VALUES_KEY, {}).get(unit_id, {})

    def restore_versicharge_energy(self, value: float) -> None:
        """Seed the energy guard from Home Assistant's restored entity state."""
        if not math.isfinite(value) or value < 0:
            return
        self._versicharge_energy_filter.seed(value)
        if not self.data:
            return
        try:
            values = self.get_versicharge_values()
        except HomeAssistantError:
            return
        current = values.get("energy_total")
        values["energy_total"] = self._versicharge_energy_filter.update(
            float(current) if isinstance(current, (int, float)) else None
        )
        self.async_update_listeners()

    @property
    def versicharge_profile(self) -> str:
        return str(self._versicharge_gateway().get("register_profile", "modern_assumed"))

    @property
    def versicharge_installation_current(self) -> int:
        gateway = self._versicharge_gateway()
        for key in ("installation_current", "rated_current"):
            value = gateway.get(key)
            if isinstance(value, int) and VERSICHARGE_MIN_CURRENT <= value <= VERSICHARGE_MAX_CURRENT:
                return value
        return 16

    @property
    def versicharge_target_power_kw(self) -> float | None:
        """Return the single user-owned power target in kW."""
        return self._versicharge_target_power_kw

    @property
    def versicharge_last_commanded_current(self) -> int | None:
        """Return the last whole-A value accepted by FC06."""
        return self._versicharge_last_commanded_current

    @property
    def versicharge_target_current(self) -> int | None:
        """Return the whole-ampere command derived from the current kW target."""
        if self._versicharge_target_power_kw is None:
            return None
        try:
            return whole_amp_current_for_power_kw(
                self._versicharge_target_power_kw,
                self.get_versicharge_values(),
                self.versicharge_installation_current,
            )
        except (HomeAssistantError, ValueError):
            return None

    @property
    def versicharge_is_enabled(self) -> bool:
        return self.versicharge_enabled_state is True

    @property
    def versicharge_enabled_state(self) -> bool | None:
        """Return the fresh Modbus pause state, or None if it is unknown."""
        try:
            values = self.get_versicharge_values()
        except HomeAssistantError:
            return None
        if not values.get("charging_current_limit_fresh", False):
            return None
        value = values.get("charging_current_limit")
        if not isinstance(value, (int, float)):
            return None
        return value >= VERSICHARGE_MIN_CURRENT

    @property
    def versicharge_current_control_available(self) -> bool:
        """Return whether this online device supports current control.

        A missed read of the isolated register 1633 must not make the target
        controls disappear.  Every identified VersiCharge profile supports
        this register; target writes still require a fresh state and every
        physical command requires a positive Modbus acknowledgement.
        """
        try:
            gateway = self._versicharge_gateway()
        except HomeAssistantError:
            return False
        unit_id = gateway.get("unit_id")
        return (
            self.last_update_success
            and isinstance(unit_id, int)
            and 1 <= unit_id <= 247
        )

    def _require_versicharge_current_control_available(self) -> None:
        if not self.versicharge_current_control_available:
            raise HomeAssistantError(
                "VersiCharge current-limit register is currently unavailable"
            )

    def _begin_versicharge_command(
        self, *, enforce_interval: bool = True
    ) -> None:
        """Start one command or fail immediately without creating a waiter."""
        self._require_versicharge_command_idle()
        now = time.monotonic()
        remaining = (
            VERSICHARGE_COMMAND_INTERVAL_SECONDS
            - (now - self._versicharge_last_command_started)
        )
        if enforce_interval and remaining > 0:
            raise HomeAssistantError(
                "VersiCharge command rate limit is active; retry in "
                f"{remaining:.1f} seconds"
            )
        self._versicharge_command_in_progress = True
        self._versicharge_last_command_started = now

    def _require_versicharge_command_idle(self) -> None:
        """Reject a concurrent command even when the new call would be a no-op."""
        if self._versicharge_command_in_progress:
            raise HomeAssistantError(
                "A VersiCharge command is already in progress; no command was queued"
            )

    def _record_versicharge_local_target_update(self) -> None:
        """Rate-limit local-only target changes without delaying a resume write."""
        now = time.monotonic()
        remaining = (
            VERSICHARGE_COMMAND_INTERVAL_SECONDS
            - (now - self._versicharge_last_local_target_update)
        )
        if remaining > 0:
            raise HomeAssistantError(
                "VersiCharge target update rate limit is active; retry in "
                f"{remaining:.1f} seconds"
            )
        self._versicharge_last_local_target_update = now

    def _end_versicharge_command(self) -> None:
        self._versicharge_command_in_progress = False

    async def _async_write_versicharge_current_once(
        self,
        current: int,
        *,
        enforce_interval: bool = True,
    ) -> None:
        """Write exactly once, require ACK and leave verification to polling."""
        gateway = self._versicharge_gateway()
        unit_id = int(gateway["unit_id"])
        raw = encode_charging_current(current)
        self._begin_versicharge_command(enforce_interval=enforce_interval)
        try:
            try:
                async with asyncio.timeout(VERSICHARGE_COMMAND_TIMEOUT_SECONDS):
                    acknowledged = await self.modbus.write_uint16(
                        unit_id, VERSICHARGE_CURRENT_REGISTER, raw
                    )
            except TimeoutError as err:
                raise HomeAssistantError(
                    "VersiCharge current command timed out; it was not retried"
                ) from err
            if not acknowledged:
                raise HomeAssistantError(
                    "VersiCharge did not positively acknowledge the current command"
                )

            # A successful FC06 response echoes the accepted whole-A command.
            # Update only the local snapshot; the next regular read-only poll
            # replaces it with the charger's independent register value.
            values = self.get_versicharge_values()
            values["charging_current_limit_raw"] = raw
            values["charging_current_limit"] = float(current)
            values["charging_current_limit_fresh"] = True
            values["charging_current_limit_source"] = "write_ack"
            self._versicharge_last_commanded_current = current
        finally:
            self._end_versicharge_command()

    async def async_set_versicharge_target_power_kw(self, value: float) -> None:
        """Apply one stable kW-to-whole-A conversion without queuing."""
        self._require_versicharge_current_control_available()
        self._require_versicharge_command_idle()
        values = self.get_versicharge_values()
        try:
            power_kw = quantize_power_kw(value)
            current = whole_amp_current_for_power_kw(
                power_kw, values, self.versicharge_installation_current
            )
        except ValueError as err:
            raise HomeAssistantError(str(err)) from err

        enabled_state = self.versicharge_enabled_state
        actual_limit = values.get("charging_current_limit")
        target_unchanged = self._versicharge_target_power_kw == power_kw
        if target_unchanged and (
            enabled_state is not True or actual_limit == current
        ):
            return
        if enabled_state is None:
            raise HomeAssistantError(
                "VersiCharge current-limit readback is unavailable; "
                "the target was not changed"
            )

        write_required = enabled_state is True and actual_limit != current
        if write_required:
            await self._async_write_versicharge_current_once(current)
        else:
            # A paused target change, or a different kW value that resolves to
            # the same whole ampere, is still one logical target transaction.
            # Rate-limit its listener fan-out separately, so setting a paused
            # target never delays the immediately following resume command.
            self._record_versicharge_local_target_update()

        # While paused this is only the explicit resume target.  While active
        # it is committed only after the write ACK (or an exact deduplication).
        self._versicharge_target_power_kw = power_kw
        self.async_update_listeners()

    async def async_set_versicharge_enabled(self, enabled: bool) -> None:
        """Pause with zero or resume the single remembered kW target."""
        self._require_versicharge_current_control_available()
        self._require_versicharge_command_idle()
        enabled_state = self.versicharge_enabled_state
        if enabled_state is not None and bool(enabled) == enabled_state:
            return

        if enabled:
            values = self.get_versicharge_values()
            power_kw = self._versicharge_target_power_kw
            if power_kw is None:
                bounds = nominal_power_bounds_kw(
                    values, self.versicharge_installation_current
                )
                if bounds is None:
                    raise HomeAssistantError(
                        "The charger phase mode is unavailable"
                    )
                power_kw = bounds[0]
            try:
                target = whole_amp_current_for_power_kw(
                    power_kw, values, self.versicharge_installation_current
                )
            except ValueError as err:
                raise HomeAssistantError(str(err)) from err
            await self._async_write_versicharge_current_once(target)
            self._versicharge_target_power_kw = power_kw
        else:
            await self._async_write_versicharge_current_once(
                0, enforce_interval=False
            )
        self.async_update_listeners()

    async def async_set_versicharge_fallback(
        self, *, current: int | None = None, timeout: int | None = None
    ) -> None:
        """Write the native fallback pair once without a command queue."""
        gateway = self._versicharge_gateway()
        unit_id = int(gateway["unit_id"])
        self._begin_versicharge_command(enforce_interval=False)
        try:
            values = self.get_versicharge_values()
            effective_current = (
                current if current is not None else values.get("fallback_current")
            )
            effective_timeout = (
                timeout if timeout is not None else values.get("fallback_time")
            )
            if not isinstance(effective_current, int) or not isinstance(
                effective_timeout, int
            ):
                raise HomeAssistantError(
                    "Fallback registers are currently unavailable"
                )
            maximum = self.versicharge_installation_current
            if effective_current != 0 and not (
                VERSICHARGE_MIN_CURRENT <= effective_current <= maximum
            ):
                raise HomeAssistantError(
                    "Fallback current must be 0 or "
                    f"{VERSICHARGE_MIN_CURRENT}..{maximum} A"
                )
            if effective_timeout != 0 and not 60 <= effective_timeout <= 600:
                raise HomeAssistantError(
                    "Fallback time must be 0 or 60..600 seconds"
                )

            requested = [effective_current, effective_timeout]
            try:
                async with asyncio.timeout(VERSICHARGE_COMMAND_TIMEOUT_SECONDS):
                    acknowledged = await self.modbus.write_registers(
                        unit_id,
                        VERSICHARGE_FALLBACK_CURRENT_REGISTER,
                        requested,
                    )
            except TimeoutError as err:
                raise HomeAssistantError(
                    "VersiCharge fallback command timed out; it was not retried"
                ) from err
            if not acknowledged:
                raise HomeAssistantError(
                    "VersiCharge did not positively acknowledge the fallback settings"
                )
            values["fallback_current"] = effective_current
            values["fallback_time"] = effective_timeout
        finally:
            self._end_versicharge_command()
        self.async_update_listeners()

    def register_powercenter_guarded_entity(self, entity: object) -> None:
        """Register a writable entity that must update on global cooldown changes."""
        self._powercenter_guarded_entities.add(entity)

    def is_unit_connected(self, slave: int) -> bool:
        """Return whether the latest successful refresh reports a connected unit."""
        if not self.last_update_success or not self.data:
            return False
        state = self.data.get(VALUES_KEY, {}).get(slave, {}).get("connection_state")
        return state == CONNECTION_STATE_MAP[3]

    def _notify_powercenter_guarded_entities(self) -> None:
        """Force all guarded write/control entities to republish availability."""
        for entity in list(self._powercenter_guarded_entities):
            writer = getattr(entity, "async_write_ha_state", None)
            if writer is None:
                continue
            try:
                writer()
            except Exception as err:  # noqa: BLE001
                _LOGGER.debug("Ignoring cooldown entity state update failure: %r", err)

    @staticmethod
    def _topology_signature(slaves: list[dict]) -> tuple[tuple[object, ...], ...]:
        """Return the entity-relevant identity of a discovered topology."""
        return tuple(
            sorted(
                (
                    item.get("slave"),
                    item.get("variant"),
                    item.get("device_type"),
                )
                for item in slaves
            )
        )

    def _schedule_topology_reload(self) -> None:
        """Reload platforms once so newly discovered capabilities get entities."""
        if self._topology_reload_task and not self._topology_reload_task.done():
            return
        self._topology_reload_task = self.hass.async_create_task(
            self._async_reload_after_topology_change()
        )

    async def _async_reload_after_topology_change(self) -> None:
        """Defer the reload until the active coordinator refresh has returned."""
        try:
            await asyncio.sleep(1)
            self._topology_reload_task = None
            await self.hass.config_entries.async_reload(self.entry.entry_id)
        except asyncio.CancelledError:
            raise
        finally:
            if self._topology_reload_task is asyncio.current_task():
                self._topology_reload_task = None

    def _is_powercenter_gateway(self) -> bool:
        """Return True when this coordinator represents a Powercenter gateway."""
        gateway = self.data.get(GATEWAY_DEVICE_KEY, {}) if self.data else {}
        return gateway.get("device_kind") == DEVICE_KIND_POWERCENTER

    def get_powercenter_write_cooldown_remaining(self) -> int:
        """Return remaining Powercenter delayed-ACK cooldown seconds."""
        remaining = self._powercenter_write_cooldown_until - time.monotonic()
        if remaining <= 0:
            return 0
        return min(ECPD_STANDBY_COOLDOWN_SECONDS, int(remaining + 0.999))

    def is_powercenter_write_cooldown_active(self) -> bool:
        """Return whether the per-gateway delayed-ACK cooldown is active."""
        return self.get_powercenter_write_cooldown_remaining() > 0

    def _start_powercenter_write_cooldown(self) -> None:
        """Start or restart the per-gateway 10s delayed-ACK cooldown."""
        if not self._is_powercenter_gateway():
            return
        self._powercenter_write_cooldown_until = time.monotonic() + ECPD_STANDBY_COOLDOWN_SECONDS
        self.async_update_listeners()
        self._notify_powercenter_guarded_entities()
        if not self._powercenter_write_cooldown_task or self._powercenter_write_cooldown_task.done():
            self._powercenter_write_cooldown_task = self.hass.async_create_task(
                self._async_run_powercenter_write_cooldown()
            )

    async def _async_run_powercenter_write_cooldown(self) -> None:
        """Run visible Powercenter delayed-ACK cooldown countdown."""
        try:
            last_remaining: int | None = None
            while True:
                remaining = self.get_powercenter_write_cooldown_remaining()
                if remaining != last_remaining:
                    last_remaining = remaining
                    self.async_update_listeners()
                    self._notify_powercenter_guarded_entities()
                if remaining <= 0:
                    break
                await asyncio.sleep(1)
        except asyncio.CancelledError:
            raise
        finally:
            if self.get_powercenter_write_cooldown_remaining() <= 0:
                self._powercenter_write_cooldown_until = 0.0
                self.async_update_listeners()
                self._notify_powercenter_guarded_entities()
            self._powercenter_write_cooldown_task = None


    def should_block_powercenter_interaction(self, *, slave: int | None = None, command: bool = False) -> bool:
        """Return True when a writable UI entity must be disabled by cooldown.

        Scope:
        - only Powercenter gateways (PAC/PAC2200 is excluded)
        - one independent timer per coordinator/config entry = one Powercenter system
        - while active: block all slave writes and all gateway/slave commands
        - while active: do not block normal gateway parameter writes
        """
        if not self._is_powercenter_gateway() or not self.is_powercenter_write_cooldown_active():
            return False
        if command:
            return True
        return slave is not None and slave != GATEWAY_SLAVE

    def _require_powercenter_write_ready(self, *, target: str) -> None:
        """Raise when a Powercenter command/write is still inside delayed-ACK cooldown."""
        if self._is_powercenter_gateway() and self.is_powercenter_write_cooldown_active():
            remaining = self.get_powercenter_write_cooldown_remaining()
            raise HomeAssistantError(
                f"Powercenter verarbeitet noch ({target}). Bitte {remaining} s warten."
            )

    def _should_delay_command(self, slave: int) -> bool:
        """Commands on Powercenter gateway and all its slaves need delayed-ACK cooldown."""
        return self._is_powercenter_gateway()

    def _should_delay_parameter_write(self, slave: int) -> bool:
        """Only writes to slaves need delayed-ACK cooldown; gateway parameter writes do not."""
        return self._is_powercenter_gateway() and slave != GATEWAY_SLAVE

    async def write_uint16_command_with_cooldown(self, slave: int, address: int, value: int) -> bool:
        """Write a command register and apply Powercenter delayed-ACK cooldown when required."""
        async with self._write_lock:
            delayed = self._should_delay_command(slave)
            if delayed:
                self._require_powercenter_write_ready(target=f"command unit={slave}")
            try:
                return await self.modbus.write_uint16_command(
                    slave=slave, address=address, value=value
                )
            finally:
                if delayed:
                    self._start_powercenter_write_cooldown()

    async def write_u8_u8_u16_command_with_cooldown(self, slave: int, address: int, first_u8: int, second_u8: int, value_u16: int) -> bool:
        """Write a packed command and apply Powercenter delayed-ACK cooldown when required."""
        async with self._write_lock:
            delayed = self._should_delay_command(slave)
            if delayed:
                self._require_powercenter_write_ready(target=f"command unit={slave}")
            try:
                return await self.modbus.write_u8_u8_u16_command(
                    slave, address, first_u8, second_u8, value_u16
                )
            finally:
                if delayed:
                    self._start_powercenter_write_cooldown()

    async def write_uint16_with_cooldown(self, slave: int, address: int, value: int) -> bool:
        """Write a parameter register and apply cooldown for Powercenter slave writes only."""
        async with self._write_lock:
            delayed = self._should_delay_parameter_write(slave)
            if delayed:
                self._require_powercenter_write_ready(target=f"write unit={slave}")
            try:
                return await self.modbus.write_uint16(slave, address, value)
            finally:
                if delayed:
                    self._start_powercenter_write_cooldown()

    async def write_float32_with_cooldown(self, slave: int, address: int, value: float) -> bool:
        """Write an FP32 parameter and apply cooldown for Powercenter slave writes only."""
        async with self._write_lock:
            delayed = self._should_delay_parameter_write(slave)
            if delayed:
                self._require_powercenter_write_ready(target=f"write unit={slave}")
            try:
                return await self.modbus.write_float32(slave, address, value)
            finally:
                if delayed:
                    self._start_powercenter_write_cooldown()

    def get_ecpd_standby_cooldown_remaining(self, slave: int) -> int:
        """Return remaining delayed-ACK cooldown seconds for compatibility."""
        return self.get_powercenter_write_cooldown_remaining()

    def is_ecpd_standby_cooldown_active(self, slave: int) -> bool:
        """Return whether Powercenter delayed-ACK cooldown is active."""
        return self.is_powercenter_write_cooldown_active()

    def start_ecpd_standby_cooldown(self, slave: int) -> None:
        """Start Powercenter delayed-ACK cooldown for compatibility."""
        self._start_powercenter_write_cooldown()

    def get_ecpd_unlock_ack_remaining(self, slave: int) -> int:
        """Return remaining local ECPD unlock acknowledge countdown seconds."""
        remaining = self._ecpd_unlock_ack_until.get(slave, 0.0) - time.monotonic()
        if remaining <= 0:
            return 0
        return min(ECPD_UNLOCK_ACK_SECONDS, int(remaining + 0.999))

    def is_ecpd_unlock_ack_active(self, slave: int) -> bool:
        """Return whether the local ECPD unlock acknowledge timer is running."""
        return self.get_ecpd_unlock_ack_remaining(slave) > 0

    def start_ecpd_unlock_ack(self, slave: int) -> None:
        """Start or restart the 90 s local ECPD unlock acknowledge timer."""
        self._ecpd_unlock_ack_until[slave] = time.monotonic() + ECPD_UNLOCK_ACK_SECONDS
        self.async_update_listeners()
        old_task = self._ecpd_unlock_ack_tasks.get(slave)
        if old_task and not old_task.done():
            old_task.cancel()
        self._ecpd_unlock_ack_tasks[slave] = self.hass.async_create_task(
            self._async_run_ecpd_unlock_ack(slave)
        )

    def reset_ecpd_unlock_ack(self, slave: int) -> None:
        """Reset the local ECPD unlock acknowledge timer."""
        self._ecpd_unlock_ack_until.pop(slave, None)
        task = self._ecpd_unlock_ack_tasks.pop(slave, None)
        if task and not task.done():
            task.cancel()
        self.async_update_listeners()

    async def _async_run_ecpd_unlock_ack(self, slave: int) -> None:
        """Run visible ECPD unlock acknowledge countdown."""
        try:
            last_remaining: int | None = None
            while True:
                remaining = self.get_ecpd_unlock_ack_remaining(slave)
                if remaining != last_remaining:
                    last_remaining = remaining
                    self.async_update_listeners()
                if remaining <= 0:
                    break
                await asyncio.sleep(1)
        except asyncio.CancelledError:
            raise
        finally:
            if self.get_ecpd_unlock_ack_remaining(slave) <= 0:
                self._ecpd_unlock_ack_until.pop(slave, None)
                self.async_update_listeners()
            current = self._ecpd_unlock_ack_tasks.get(slave)
            if current is asyncio.current_task():
                self._ecpd_unlock_ack_tasks.pop(slave, None)

    async def _async_run_ecpd_standby_cooldown(self, slave: int) -> None:
        """Run visible 10 -> 0 second ECPD standby cooldown countdown."""
        try:
            for remaining in range(ECPD_STANDBY_COOLDOWN_SECONDS - 1, -1, -1):
                await asyncio.sleep(1)
                self._ecpd_standby_cooldown_remaining[slave] = remaining
                self.async_update_listeners()
        except asyncio.CancelledError:
            raise
        finally:
            if self._ecpd_standby_cooldown_remaining.get(slave, 0) != 0:
                self._ecpd_standby_cooldown_remaining[slave] = 0
                self.async_update_listeners()
            self._ecpd_standby_cooldown_tasks.pop(slave, None)


    def is_device_test_running(self, slave: int, kind: str = "ecpd") -> bool:
        """Return whether a device test is assumed to be running for one slave and kind."""
        return self._test_running.get((slave, kind), False)

    def is_ecpd_device_test_running(self, slave: int) -> bool:
        """Backward-compatible ECPD test-running helper."""
        return self.is_device_test_running(slave, "ecpd")

    def start_device_test_tracking(self, slave: int, *, kind: str, status_key: str, timestamp_key: str) -> None:
        """Start derived test-running tracking for one slave and one test kind."""
        track_key = (slave, kind)
        values = self.data.get(VALUES_KEY, {}) if self.data else {}
        device_values = values.get(slave, {})
        self._test_baseline[track_key] = (device_values.get(status_key), device_values.get(timestamp_key))
        self._test_started_at[track_key] = datetime.now(timezone.utc)
        self._test_running[track_key] = True
        self.async_update_listeners()

        old_task = self._test_timeout_tasks.pop(track_key, None)
        if old_task and not old_task.done():
            old_task.cancel()
        self._test_timeout_tasks[track_key] = self.hass.async_create_task(
            self._async_stop_device_test_tracking_after_timeout(track_key)
        )

    def start_ecpd_device_test_tracking(self, slave: int) -> None:
        """Backward-compatible ECPD test tracking helper."""
        self.start_device_test_tracking(
            slave,
            kind="ecpd",
            status_key="device_test_status",
            timestamp_key="device_test_timestamp",
        )

    def cancel_device_test_tracking(self, slave: int, kind: str) -> None:
        """Cancel local test tracking after a command was not acknowledged."""
        track_key = (slave, kind)
        self._test_running.pop(track_key, None)
        self._test_baseline.pop(track_key, None)
        self._test_started_at.pop(track_key, None)
        task = self._test_timeout_tasks.pop(track_key, None)
        if task and not task.done():
            task.cancel()
        self.async_update_listeners()

    async def _async_stop_device_test_tracking_after_timeout(self, track_key: tuple[int, str]) -> None:
        """Stop derived test-running tracking if no register change arrives."""
        this_task = asyncio.current_task()
        try:
            await asyncio.sleep(90)
            if self._test_running.get(track_key, False):
                self._test_running[track_key] = False
                self.async_update_listeners()
        except asyncio.CancelledError:
            raise
        finally:
            if self._test_timeout_tasks.get(track_key) is this_task:
                self._test_timeout_tasks.pop(track_key, None)

    def restore_test_display_values(self, slave: int, *, kind: str, status_key: str, timestamp_key: str, timestamp_value: datetime) -> None:
        """Restore locally derived/latched test timestamp after integration reload."""
        if timestamp_value is None:
            return
        values = self.data.get(VALUES_KEY, {}) if self.data else {}
        device_values = values.get(slave, {})
        status_value = device_values.get(status_key)
        track_key = (slave, kind)
        cached_status, cached_timestamp = self._test_display_cache.get(track_key, (None, None))
        if cached_timestamp is None:
            self._test_display_cache[track_key] = (status_value or cached_status, timestamp_value)
            self.async_update_listeners()

    def get_test_display_values(self, slave: int, *, kind: str, status_key: str, timestamp_key: str) -> tuple[object, object]:
        """Return display values scoped to one slave and one test kind.

        ECPD exposes a native timestamp register, so the current register value
        is used directly. RCM has no native timestamp; its value is derived
        locally and restored into the display cache after reload.
        """
        values = self.data.get(VALUES_KEY, {}) if self.data else {}
        device_values = values.get(slave, {})
        current = (device_values.get(status_key), device_values.get(timestamp_key))
        track_key = (slave, kind)

        if kind == "ecpd":
            return current

        if track_key in self._test_display_cache:
            cached_status, cached_timestamp = self._test_display_cache[track_key]
            if cached_status is None and device_values.get(status_key) is not None:
                cached_status = device_values.get(status_key)
            self._test_display_cache[track_key] = (cached_status, cached_timestamp)
            return self._test_display_cache[track_key]

        if any(value is not None for value in current):
            self._test_display_cache[track_key] = current

        return self._test_display_cache.get(track_key, current)

    def _update_ecpd_unlock_ack_tracking(self, values: dict[int, dict]) -> None:
        """Stop local ECPD unlock acknowledge timer after physical acknowledge."""
        for slave, device_values in values.items():
            if device_values.get("unlock_status") == 1 and self.is_ecpd_unlock_ack_active(slave):
                self.reset_ecpd_unlock_ack(slave)


    def _update_device_test_tracking(self, values: dict[int, dict]) -> None:
        """Stop tracking and update display cache only for the active slave."""
        changed = False
        kind_keys = {
            "ecpd": ("device_test_status", "device_test_timestamp"),
            "rcm": ("rcm_test_status", "rcm_test_timestamp"),
        }

        for track_key, baseline in list(self._test_baseline.items()):
            slave, kind = track_key
            if not self._test_running.get(track_key, False):
                continue
            status_key, timestamp_key = kind_keys.get(kind, (None, None))
            if not status_key or not timestamp_key:
                continue

            device_values = values.get(slave, {})
            status_value = device_values.get(status_key)
            timestamp_value = device_values.get(timestamp_key)
            current = (status_value, timestamp_value)
            has_current_value = any(value is not None for value in current)
            completed = current != baseline and has_current_value

            # RCM devices expose a test result but no reliable native timestamp.
            # If the result value is identical before and after a test, there is no
            # Modbus value change to observe. Keep "Test wird durchgeführt" briefly
            # and then accept the current final result as completion of this command.
            if not completed and kind == "rcm" and status_value in {
                "Test erfolgreich",
                "Test fehlgeschlagen",
                "Test abgebrochen",
            }:
                started_at = self._test_started_at.get(track_key)
                if started_at and datetime.now(timezone.utc) - started_at >= timedelta(seconds=3):
                    completed = True

            if completed:
                if kind == "rcm" and status_value is not None and timestamp_value is None:
                    current = (
                        status_value,
                        datetime.now(timezone.utc).replace(second=0, microsecond=0),
                    )

                self._test_running[track_key] = False
                self._test_baseline.pop(track_key, None)
                self._test_started_at.pop(track_key, None)
                self._test_display_cache[track_key] = current
                task = self._test_timeout_tasks.pop(track_key, None)
                if task and not task.done():
                    task.cancel()
                changed = True

        if changed:
            self.async_update_listeners()

    def _update_ecpd_device_test_tracking(self, values: dict[int, dict]) -> None:
        """Backward-compatible wrapper for derived test tracking."""
        self._update_device_test_tracking(values)

    async def async_shutdown(self) -> None:
        """Stop runtime tasks and close the Modbus connection."""
        await super().async_shutdown()
        for task in list(self._ecpd_standby_cooldown_tasks.values()):
            task.cancel()
        for task in list(self._ecpd_unlock_ack_tasks.values()):
            task.cancel()
        if self._powercenter_write_cooldown_task and not self._powercenter_write_cooldown_task.done():
            self._powercenter_write_cooldown_task.cancel()
        self._powercenter_write_cooldown_task = None
        self._powercenter_write_cooldown_until = 0.0
        if self._topology_reload_task and not self._topology_reload_task.done():
            self._topology_reload_task.cancel()
        self._topology_reload_task = None
        for task in list(self._test_timeout_tasks.values()):
            task.cancel()
        self._ecpd_standby_cooldown_tasks.clear()
        self._ecpd_standby_cooldown_remaining.clear()
        self._ecpd_unlock_ack_tasks.clear()
        self._ecpd_unlock_ack_until.clear()
        self._test_timeout_tasks.clear()
        self._test_running.clear()
        self._test_baseline.clear()
        self._test_display_cache.clear()
        self._test_started_at.clear()
        self._versicharge_command_in_progress = False
        self._root_gateway = None
        self._cached_slaves.clear()
        self._next_discovery_at = 0.0
        await self.modbus.async_close()

    def _merge_slave_online_state(self, discovered_slaves: list[dict]) -> list[dict]:
        """Keep discovered end devices without deriving a separate local online state.

        The user-visible connectivity state is sourced exclusively from the
        gateway connection-state registers (slave 255) and exposed as the
        diagnostic Verbindungsstatus sensor per end device.
        """
        previous_slaves = self.data.get(SLAVES_KEY, []) if self.data else []
        merged: dict[int, dict] = {item["slave"]: dict(item) for item in previous_slaves}

        for slave_info in discovered_slaves:
            slave = slave_info["slave"]
            merged[slave] = dict(slave_info)

        for slave_info in merged.values():
            slave_info.pop("online", None)

        return list(sorted(merged.values(), key=lambda item: item["slave"]))

    def _apply_value_based_online_state(
        self,
        slaves: list[dict],
        values: dict,
    ) -> list[dict]:
        """Do not derive an additional online/offline state from end-device values."""
        for slave_info in slaves:
            slave_info.pop("online", None)
        return slaves

    async def async_setup(self) -> None:
        """Open the TCP connection; the coordinator first refresh loads data."""
        connected = await self.modbus.async_connect()
        if not connected:
            raise ConfigEntryNotReady(
                f"Keine Verbindung zum Siemens SENTRON Gateway {self.host}:{self.port}"
            )

        if GATEWAY_STARTUP_DELAY > 0:
            _LOGGER.info(
                "Siemens SENTRON Gateway %s:%s verbunden, warte %s Sekunden auf Initialisierung",
                self.host,
                self.port,
                GATEWAY_STARTUP_DELAY,
            )
            await asyncio.sleep(GATEWAY_STARTUP_DELAY)

    async def _async_update_data(self) -> dict:
        successful_reads_before = self.modbus.successful_read_count
        try:
            initial_refresh = self._root_gateway is None
            if initial_refresh:
                gateway = await async_build_gateway_data(
                    modbus=self.modbus,
                    entry_id=self.entry.entry_id,
                    host=self.host,
                    port=self.port,
                    name=self.name,
                    device_kind=self.entry.data.get("device_kind"),
                    modbus_unit_id=self.entry.data.get("modbus_unit_id"),
                )
                root_gateway = dict(gateway)
            else:
                # Device kind, model, serial number, firmware and addressing do
                # not change during a config-entry lifetime.  Reusing this
                # snapshot also prevents a temporary PAC probe failure from
                # changing the root into a Powercenter (or vice versa).
                gateway = dict(self._root_gateway)
                root_gateway = self._root_gateway

            if is_pac2200_root(gateway):
                slaves: list[dict] = []
                values = await self._async_read_pac2200_values()
            elif is_versicharge_root(gateway):
                slaves = []
                unit_id = int(gateway["unit_id"])
                # Identification and firmware values were read during initial
                # discovery and do not change during this config-entry life.
                # The regular cycle is read-only and never shares a command
                # lock, so failed Modbus requests cannot accumulate writers.
                device_values = {
                    key: gateway.get(key)
                    for key in VERSICHARGE_STATIC_VALUE_KEYS
                    if key in gateway
                }
                device_values.update(
                    await async_read_versicharge_values(
                        self.modbus,
                        unit_id,
                        profile=str(
                            gateway.get("register_profile", "modern_assumed")
                        ),
                        state_profile=str(
                            gateway.get("state_profile", "modern_assumed")
                        ),
                    )
                )
                device_values["charging_current_limit_fresh"] = isinstance(
                    device_values.get("charging_current_limit"), (int, float)
                )
                device_values["charging_current_limit_source"] = (
                    "poll"
                    if device_values["charging_current_limit_fresh"]
                    else None
                )

                device_values["energy_total"] = self._versicharge_energy_filter.update(
                    device_values.get("energy_total")
                )
                raw_phase = device_values.get("charger_phase_raw")
                if raw_phase in {0, 1}:
                    # Register 1642 reports the stable charger type. Phase
                    # currents remain monitoring-only because a transient
                    # zero on L2/L3 must never change a power command by 3×.
                    self._versicharge_effective_phase_count = (
                        1 if raw_phase == 0 else 3
                    )
                device_values["effective_phase_count"] = (
                    self._versicharge_effective_phase_count
                )
                installation_current = self.versicharge_installation_current if self.data else next(
                    (
                        int(gateway[key])
                        for key in ("installation_current", "rated_current")
                        if isinstance(gateway.get(key), int)
                        and VERSICHARGE_MIN_CURRENT <= int(gateway[key]) <= VERSICHARGE_MAX_CURRENT
                    ),
                    16,
                )
                minimum_power = power_for_current(
                    VERSICHARGE_MIN_CURRENT, device_values
                )
                maximum_power = power_for_current(
                    installation_current, device_values
                )
                device_values["minimum_charging_power"] = (
                    round(minimum_power) if minimum_power is not None else None
                )
                device_values["maximum_charging_power"] = (
                    round(maximum_power) if maximum_power is not None else None
                )

                # Initialize the UI target once. Later telemetry and register
                # readback never back-convert or alter this user-owned value.
                if self._versicharge_target_power_kw is None:
                    bounds_kw = nominal_power_bounds_kw(
                        device_values, installation_current
                    )
                    if bounds_kw is not None:
                        actual_limit = device_values.get(
                            "charging_current_limit"
                        )
                        if (
                            isinstance(actual_limit, (int, float))
                            and actual_limit >= VERSICHARGE_MIN_CURRENT
                        ):
                            initial_current = min(
                                max(
                                    int(float(actual_limit) + 0.5),
                                    VERSICHARGE_MIN_CURRENT,
                                ),
                                installation_current,
                            )
                            self._versicharge_target_power_kw = (
                                nominal_power_kw_for_current(
                                    initial_current,
                                    int(device_values["effective_phase_count"]),
                                )
                            )
                        else:
                            self._versicharge_target_power_kw = bounds_kw[0]
                values = {unit_id: device_values}
            elif is_powercenter_root(gateway):
                await self._async_read_gateway_values(gateway)

                now = time.monotonic()
                if initial_refresh or now >= self._next_discovery_at:
                    discovered_slaves = await async_discover_slaves(self.modbus, gateway)
                    slaves = self._merge_slave_online_state(discovered_slaves)
                    self._next_discovery_at = now + _DISCOVERY_INTERVAL_SECONDS
                    if (
                        not initial_refresh
                        and self._topology_signature(slaves)
                        != self._topology_signature(self._cached_slaves)
                    ):
                        _LOGGER.info(
                            "SENTRON topology changed; scheduling config-entry reload"
                        )
                        self._schedule_topology_reload()
                else:
                    slaves = [dict(item) for item in self._cached_slaves]

                values = await self._async_read_all_values(slaves, gateway)
            else:
                raise UpdateFailed(
                    f"Unbekannter SENTRON Root-Gerätetyp: {gateway.get('device_kind')!r}"
                )

            if self.modbus.successful_read_count == successful_reads_before:
                raise UpdateFailed(
                    f"Keine gültige Modbus-Antwort von {self.host}:{self.port}"
                )

            if is_powercenter_root(gateway):
                self._update_ecpd_device_test_tracking(values)
                self._update_ecpd_unlock_ack_tracking(values)
            slaves = self._apply_value_based_online_state(slaves, values)

            gateway["online"] = True
            if initial_refresh:
                self._root_gateway = root_gateway
            self._cached_slaves = [dict(item) for item in slaves]

            return {
                GATEWAY_DEVICE_KEY: gateway,
                SLAVES_KEY: slaves,
                VALUES_KEY: values,
            }
        except UpdateFailed:
            raise
        except Exception as err:  # noqa: BLE001
            raise UpdateFailed(f"Update fehlgeschlagen: {err}") from err

    async def _async_read_gateway_values(self, gateway: dict) -> None:
        """Read gateway-native diagnosis and metering values from slave 255."""
        # Root identity and Device Variant are deliberately not re-detected here.
        # They are immutable for the lifetime of the config entry.
        gateway["alarm_state"] = await self.modbus.read_input_u32(GATEWAY_SLAVE, 2559)
        operating_hours = await self.modbus.read_input_float64(GATEWAY_SLAVE, 2577)
        gateway["operating_hours_overall"] = None if operating_hours is None else operating_hours / 3600
        gateway["ble_signal_strength_rssi"] = await self.modbus.read_input_i16(GATEWAY_SLAVE, 2620)
        gateway["radio_channel"] = await self.modbus.read_input_u16(GATEWAY_SLAVE, 2632)
        gateway["temperature"] = await self.modbus.read_input_float32(GATEWAY_SLAVE, 3071)
        gateway["average_temperature"] = await self.modbus.read_input_float32(GATEWAY_SLAVE, 3073)

    def _gateway_enddevice_address(self, gateway: dict, slave: int, value_key: str) -> int | None:
        """Return gateway-side status register address for one end device."""
        index = max(slave - 1, 0)
        variant = gateway.get("variant")
        model = str(gateway.get("model", ""))

        if value_key == "connection_state":
            if variant in (14, 16) or "1100" in model or "2000" in model:
                return GATEWAY_POC1100_CONNECTION_STATE_BASE + index
            return GATEWAY_POC1000_CONNECTION_STATE_BASE + index

        if value_key == "breaker_state":
            if variant in (14, 16) or "1100" in model or "2000" in model:
                return GATEWAY_POC1100_BREAKER_STATE_BASE + index
            return None

        return None

    async def _read_gateway_enddevice_u16(self, gateway: dict, slave: int, value_key: str) -> int | None:
        address = self._gateway_enddevice_address(gateway, slave, value_key)
        if address is None:
            return None
        return await self.modbus.read_input_u16(GATEWAY_SLAVE, address)

    async def _read_powercenter_dependent_breaker_state(self, gateway: dict, slave: int) -> int | None:
        """Read Breaker State from the correct source for the hosting Powercenter.

        Powercenter 1000: end-device slave, register 3110 with offset -1 => address 3109.
        Powercenter 1100/2000: gateway slave 255, gateway slot register.
        """
        if is_powercenter_1100_or_2000(gateway):
            return await self._read_gateway_enddevice_u16(gateway, slave, "breaker_state")
        return await self.modbus.read_input_u16(slave, 3109)

    async def _async_read_pac2200_values(self) -> dict[int, dict]:
        """Read the standalone PAC2200 data model from the direct PAC device."""
        device_values: dict[str, object] = {}

        for item in PAC2200_SENSORS:
            value = None

            if item.kind == "input_float32":
                value = await self.modbus.read_input_float32(PAC2200_SLAVE_ID, item.address)
            elif item.kind == "input_float64":
                value = await self.modbus.read_input_float64(PAC2200_SLAVE_ID, item.address)
            elif item.kind == "input_u32":
                value = await self.modbus.read_input_u32(PAC2200_SLAVE_ID, item.address)
            elif item.kind == "input_unix_time":
                raw = await self.modbus.read_input_u32(PAC2200_SLAVE_ID, item.address)
                if raw is not None and raw > 0:
                    try:
                        value = datetime.fromtimestamp(raw, tz=timezone.utc)
                    except (OverflowError, OSError, ValueError):
                        value = None

            if value is not None and item.scale is not None and isinstance(value, (int, float)):
                value = value * item.scale

            device_values[item.key] = value

        return {PAC2200_SLAVE_ID: device_values}


    async def _async_read_all_values(self, slaves: list[dict], gateway: dict) -> dict:
        result: dict[int, dict] = {}

        for slave_info in slaves:
            slave = slave_info["slave"]
            profile = get_effective_device_profile(slave_info)
            device_values: dict[str, object] = {}

            # Always preserve the gateway-side connection state for retained
            # topology entries. Explicitly offline units are not queried
            # directly, avoiding long timeouts and stale operational values.
            connection_raw = await self._read_gateway_enddevice_u16(
                gateway, slave, "connection_state"
            )
            device_values["connection_state"] = (
                None
                if connection_raw is None
                else CONNECTION_STATE_MAP.get(
                    connection_raw, f"Unknown ({connection_raw})"
                )
            )
            if connection_raw is not None and connection_raw != 3:
                result[slave] = device_values
                continue

            for item in profile:
                if item["key"] == "connection_state":
                    continue
                kind = item["kind"]
                address = item.get("address")
                count = item.get("count", 2)
                read_slave = item.get("slave_override", slave)
                value = None

                if kind == "input_float32":
                    value = await self.modbus.read_input_float32(read_slave, address)
                elif kind == "input_float64":
                    value = await self.modbus.read_input_float64(read_slave, address)
                elif kind == "input_u16":
                    value = await self.modbus.read_input_u16(read_slave, address)
                elif kind == "input_i16":
                    value = await self.modbus.read_input_i16(read_slave, address)
                elif kind == "gateway_breaker_state":
                    value = await self._read_powercenter_dependent_breaker_state(gateway, slave)
                elif kind == "input_u32":
                    value = await self.modbus.read_input_u32(read_slave, address)
                elif kind == "input_output_forcing":
                    value = await self.modbus.read_input_output_forcing(read_slave, address)
                elif kind == "holding_u32":
                    value = await self.modbus.read_holding_u32(read_slave, address)
                elif kind == "holding_u16":
                    value = await self.modbus.read_holding_u16(read_slave, address)
                elif kind == "input_unix_time":
                    raw = await self.modbus.read_input_u32(read_slave, address)
                    if raw is not None and raw > 0:
                        try:
                            value = datetime.fromtimestamp(raw, tz=timezone.utc)
                        except (OverflowError, OSError, ValueError):
                            value = None
                elif kind == "input_bool":
                    raw = await self.modbus.read_input_u16(read_slave, address)
                    value = None if raw is None else bool(raw)
                elif kind == "input_u16_match":
                    raw = await self.modbus.read_input_u16(read_slave, address)
                    matches = item.get("matches", [])
                    value = None if raw is None else raw in matches
                elif kind == "gateway_breaker_state_match":
                    raw = await self._read_powercenter_dependent_breaker_state(gateway, slave)
                    matches = item.get("matches", [])
                    value = None if raw is None else raw in matches
                elif kind == "input_u16_mask":
                    raw = await self.modbus.read_input_u16(read_slave, address)
                    mask = item.get("mask", 0)
                    value = None if raw is None else bool(raw & mask)
                elif kind == "input_u32_mask":
                    raw = await self.modbus.read_input_u32(read_slave, address)
                    mask = item.get("mask", 0)
                    value = None if raw is None else bool(raw & mask)
                elif kind == "holding_firmware":
                    value = await self.modbus.read_holding_firmware_version(
                        slave,
                        address,
                        count=count,
                    )

                if item["key"] == "rca_handle_state":
                    device_values["rca_handle_state_raw"] = value

                if value is not None and "scale" in item and isinstance(value, (int, float)):
                    value = value * item["scale"]

                if item["key"] == "breaker_state" and isinstance(value, int):
                    value = BREAKER_STATE_MAP.get(value, f"Unknown ({value})")
                elif item["key"] == "rca_handle_state" and isinstance(value, int):
                    value = RCA_HANDLE_STATE_MAP.get(value, f"Unknown ({value})")
                elif item["key"] == "connection_state" and isinstance(value, int):
                    value = CONNECTION_STATE_MAP.get(value, f"Unknown ({value})")
                elif item["key"] == "device_state" and isinstance(value, int):
                    value = DEVICE_STATE_MAP.get(value, f"Unknown ({value})")
                elif item["key"] == "alarm_state" and isinstance(value, int) and item.get("kind") != "input_u32":
                    value = ALARM_STATE_MAP.get(value, f"Unknown ({value})")
                elif item["key"] in ("device_test_status", "rcm_test_status") and isinstance(value, int):
                    value = {
                        0: "Unbekannt",
                        1: "Test erfolgreich",
                        2: "Test fehlgeschlagen",
                        3: "Test nicht ausgeführt",
                        4: "Test abgebrochen",
                    }.get(value, f"Unknown ({value})")
                device_values[item["key"]] = value

            if slave_info.get("variant") in (11,):
                # ECPD RCM configuration registers (holding, Siemens register offset -1 applied).
                device_values["rcm_ac_pre_alarm_enabled"] = await self.modbus.read_holding_u16(slave, 5134)
                device_values["rcm_ac_alarm_enabled"] = await self.modbus.read_holding_u16(slave, 5135)
                device_values["rcm_ac_pre_alarm_threshold_percent"] = await self.modbus.read_holding_float32(slave, 5136)
                alarm_a = await self.modbus.read_holding_float32(slave, 5138)
                device_values["rcm_ac_alarm_threshold_ma"] = None if alarm_a is None else alarm_a * 1000

                # ECPD protected configuration parameters (holding, Siemens register offset -1 applied).
                device_values["ecpd_nominal_current"] = await self.modbus.read_holding_u16(slave, 5375)
                device_values["ecpd_instantaneous_trip_behaviour"] = await self.modbus.read_holding_u16(slave, 5379)
                device_values["ecpd_time_delay_release_behaviour"] = await self.modbus.read_holding_u16(slave, 5380)
                device_values["ecpd_rcd_sensitivity"] = await self.modbus.read_holding_u16(slave, 5382)
                device_values["ecpd_rcd_tripping_time"] = await self.modbus.read_holding_u16(slave, 5383)
                device_values["ecpd_residual_current_trip_behaviour"] = await self.modbus.read_holding_u16(slave, 5384)

            if slave_info.get("variant") in MCB_RCM_VARIANTS:
                # 5SL6 COM MCB RCM configuration registers (holding, Siemens register offset -1 applied).
                device_values["rcm_rms_pre_alarm_enabled"] = await self.modbus.read_holding_u16(slave, 5140)
                device_values["rcm_rms_alarm_enabled"] = await self.modbus.read_holding_u16(slave, 5141)
                device_values["rcm_rms_pre_alarm_threshold_percent"] = await self.modbus.read_holding_float32(slave, 5142)
                device_values["rcm_rms_alarm_threshold_a"] = await self.modbus.read_holding_float32(slave, 5144)

            if slave_info.get("variant") in RCA_CONFIG_VARIANTS:
                # 5ST3 COM configuration register (holding, Siemens register offset -1 applied).
                device_values["attached_device_type"] = await self.modbus.read_holding_u16(slave, 110)

            if slave_info.get("variant") in RCA_SWITCH_VARIANTS:
                # 5ST3 COM RCA configuration registers (holding, Siemens register offset -1 applied).
                device_values["ard_enabled"] = await self.modbus.read_holding_u16(slave, 3680)
                device_values["remote_control_selector"] = await self.modbus.read_holding_u16(slave, 3690)

            result[slave] = device_values

        return result
