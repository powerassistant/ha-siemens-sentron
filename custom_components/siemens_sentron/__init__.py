"""The Siemens SENTRON integration."""

from __future__ import annotations

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr

from .const import DOMAIN, GATEWAY_DEVICE_KEY, MANUFACTURER, get_device_configuration_url
from .coordinator import SentronCoordinator
from .entity_ids import CONFIG_ENTRY_MINOR_VERSION, ENTITY_ID_MIGRATION_PENDING
from homeassistant.helpers import config_validation as cv

CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)

PLATFORMS: list[Platform] = [
    Platform.SENSOR,
    Platform.BINARY_SENSOR,
    Platform.SWITCH,
    Platform.BUTTON,
    Platform.NUMBER,
    Platform.SELECT,
]


async def async_setup(hass: HomeAssistant, config: dict) -> bool:
    """Set up Siemens SENTRON."""
    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Siemens SENTRON from a config entry."""
    coordinator = SentronCoordinator(hass, entry)
    try:
        await coordinator.async_setup()
        await coordinator.async_config_entry_first_refresh()
    except Exception:
        # The coordinator is not yet registered in hass.data, so the normal
        # unload path cannot close a socket opened before a failed first poll.
        await coordinator.async_shutdown()
        raise

    try:
        gateway = coordinator.data[GATEWAY_DEVICE_KEY]
        hardware_revision = gateway.get("hardware_revision")
        gateway_device = dr.async_get(hass).async_get_or_create(
            config_entry_id=entry.entry_id,
            identifiers={(DOMAIN, gateway["id"])},
            manufacturer=MANUFACTURER,
            model=gateway["model"],
            name=gateway["name"],
            sw_version=gateway.get("firmware"),
            hw_version=(
                str(hardware_revision) if hardware_revision is not None else None
            ),
            serial_number=gateway.get("serial_number"),
            configuration_url=get_device_configuration_url(
                gateway, gateway=gateway, prefer_local=True
            ),
        )
        coordinator.gateway_device_registry_id = gateway_device.id
    except Exception:
        await coordinator.async_shutdown()
        raise

    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN][entry.entry_id] = coordinator
    try:
        await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    except Exception:
        hass.data.get(DOMAIN, {}).pop(entry.entry_id, None)
        if not hass.data.get(DOMAIN):
            hass.data.pop(DOMAIN, None)
        await coordinator.async_shutdown()
        raise

    return True


async def async_migrate_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Migrate config data without renaming existing entity registry IDs."""
    if entry.version == 1 and (
        entry.minor_version < CONFIG_ENTRY_MINOR_VERSION
        or entry.data.get(ENTITY_ID_MIGRATION_PENDING)
    ):
        new_data = dict(entry.data)
        new_data.pop(ENTITY_ID_MIGRATION_PENDING, None)
        hass.config_entries.async_update_entry(
            entry,
            data=new_data,
            minor_version=CONFIG_ENTRY_MINOR_VERSION,
            version=1,
        )
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload Siemens SENTRON config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)

    if unload_ok:
        coordinator: SentronCoordinator | None = hass.data.get(DOMAIN, {}).pop(entry.entry_id, None)
        if coordinator is not None:
            await coordinator.async_shutdown()
        if not hass.data.get(DOMAIN):
            hass.data.pop(DOMAIN, None)

    return unload_ok
