"""Diagnostics support for Siemens SENTRON config entries."""

from __future__ import annotations

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST
from homeassistant.core import HomeAssistant

from .const import DOMAIN, GATEWAY_DEVICE_KEY, SLAVES_KEY, VALUES_KEY
from .coordinator import SentronCoordinator


TO_REDACT = {
    CONF_HOST,
    "serial_number",
    "id",
}


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: ConfigEntry
) -> dict:
    """Return decoded state while removing network and device identifiers."""
    coordinator: SentronCoordinator = hass.data[DOMAIN][entry.entry_id]
    data = coordinator.data or {}
    interval = coordinator.update_interval
    payload = {
        "config_entry": dict(entry.data),
        "coordinator": {
            "last_update_success": coordinator.last_update_success,
            "update_interval_seconds": (
                interval.total_seconds() if interval is not None else None
            ),
        },
        "root_device": dict(data.get(GATEWAY_DEVICE_KEY, {})),
        "downstream_devices": [
            dict(item) for item in data.get(SLAVES_KEY, [])
        ],
        "decoded_values": {
            str(unit_id): dict(values)
            for unit_id, values in data.get(VALUES_KEY, {}).items()
        },
    }
    return async_redact_data(payload, TO_REDACT)

