"""Binary sensor platform for Siemens SENTRON."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN, GATEWAY_DEVICE_KEY, VALUES_KEY
from .coordinator import SentronCoordinator
from .device_types import DEVICE_KIND_VERSICHARGE, is_versicharge_root
from .sensor import SentronBaseEntity


@dataclass(frozen=True, slots=True)
class VersiChargeBinarySensorDescription:
    """Description of a binary signal derived from VersiCharge telemetry."""

    key: str
    device_class: BinarySensorDeviceClass
    value_fn: Callable[[dict], bool | None]
    entity_category: EntityCategory | None = None
    icon: str | None = None
    enabled_default: bool = True


def _vehicle_connected(values: dict) -> bool | None:
    evse_state = values.get("evse_state")
    ocpp_state = values.get("ocpp_state")
    if evse_state is None and ocpp_state is None:
        return None
    return evse_state in {"connected", "charging"} or ocpp_state in {
        "preparing",
        "charging",
        "suspended_ev",
        "suspended_evse",
        "finishing",
    }


def _charging(values: dict) -> bool | None:
    evse_state = values.get("evse_state")
    ocpp_state = values.get("ocpp_state")
    active_power = values.get("active_power_total")
    if evse_state is None and ocpp_state is None and active_power is None:
        return None
    return (
        evse_state == "charging"
        or ocpp_state == "charging"
        or (
            isinstance(active_power, (int, float))
            and active_power > 100
        )
    )


def _problem(values: dict) -> bool | None:
    error_code = values.get("error_code")
    evse_state = values.get("evse_state")
    ocpp_state = values.get("ocpp_state")
    if error_code is None and evse_state is None and ocpp_state is None:
        return None
    return (
        (isinstance(error_code, int) and error_code != 0)
        or evse_state in {"recoverable_fault", "non_recoverable_fault"}
        or ocpp_state == "faulted"
    )


VERSICHARGE_BINARY_SENSORS = (
    VersiChargeBinarySensorDescription(
        key="vehicle_connected",
        device_class=BinarySensorDeviceClass.PLUG,
        value_fn=_vehicle_connected,
    ),
    VersiChargeBinarySensorDescription(
        key="charging",
        device_class=BinarySensorDeviceClass.BATTERY_CHARGING,
        value_fn=_charging,
    ),
    VersiChargeBinarySensorDescription(
        key="problem",
        device_class=BinarySensorDeviceClass.PROBLEM,
        value_fn=_problem,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up VersiCharge binary sensors and fail closed for other roots."""
    coordinator: SentronCoordinator = hass.data[DOMAIN][entry.entry_id]
    gateway = coordinator.data.get(GATEWAY_DEVICE_KEY, {})
    if not is_versicharge_root(gateway):
        return

    async_add_entities(
        VersiChargeBinarySensorEntity(coordinator, entry, description)
        for description in VERSICHARGE_BINARY_SENSORS
    )


class VersiChargeBinarySensorEntity(SentronBaseEntity, BinarySensorEntity):
    """Binary sensor belonging directly to the VersiCharge root."""

    def __init__(
        self,
        coordinator: SentronCoordinator,
        entry: ConfigEntry,
        description: VersiChargeBinarySensorDescription,
    ) -> None:
        super().__init__(coordinator, entry)
        gateway = coordinator.data[GATEWAY_DEVICE_KEY]
        if not is_versicharge_root(gateway):
            raise ValueError("VersiCharge binary sensor requires a VersiCharge root")

        self.description = description
        self._unit_id = int(gateway["unit_id"])
        self._attr_translation_key = f"versicharge_{description.key}"
        self._attr_unique_id = f"{entry.entry_id}_versicharge_{description.key}"
        self._attr_device_class = description.device_class
        self._attr_entity_category = description.entity_category
        self._attr_icon = description.icon
        self._attr_entity_registry_enabled_default = description.enabled_default

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
    def is_on(self) -> bool | None:
        values = self.coordinator.data.get(VALUES_KEY, {}).get(self._unit_id, {})
        return self.description.value_fn(values)
