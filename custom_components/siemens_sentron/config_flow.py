"""Config flow for Siemens SENTRON."""

from __future__ import annotations

import logging

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.const import CONF_HOST, CONF_PORT

from .const import DEFAULT_PORT, DOMAIN
from .device_types import (
    DEVICE_KIND_PAC2200,
    DEVICE_KIND_POWERCENTER,
    DEVICE_KIND_VERSICHARGE,
)
from .entity_ids import CONFIG_ENTRY_MINOR_VERSION
from .gateway import (
    async_detect_root_device,
    gateway_model_from_variant,
)
from .modbus_api import SentronModbusApi
from .versicharge import VERSICHARGE_DEFAULT_UNIT_ID

_LOGGER = logging.getLogger(__name__)

CONF_DEVICE_KIND = "device_kind"
CONF_MODBUS_UNIT_ID = "modbus_unit_id"


class SiemensSentronConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Siemens SENTRON."""

    VERSION = 1
    MINOR_VERSION = CONFIG_ENTRY_MINOR_VERSION

    async def async_step_user(self, user_input=None):
        """Handle the initial step."""
        errors: dict[str, str] = {}

        if user_input is not None:
            host = user_input[CONF_HOST].strip()
            port = user_input[CONF_PORT]
            modbus_unit_id = user_input.get(
                CONF_MODBUS_UNIT_ID, VERSICHARGE_DEFAULT_UNIT_ID
            )

            await self.async_set_unique_id(f"{host.casefold()}:{port}")
            self._abort_if_unique_id_configured()

            modbus = SentronModbusApi(host, port, timeout=15)
            try:
                connected = await modbus.async_connect()
                if not connected:
                    errors["base"] = "cannot_connect"
                else:
                    detection = await async_detect_root_device(
                        modbus,
                        modbus_unit_id=modbus_unit_id,
                    )
                    if detection is None:
                        errors["base"] = "unsupported_device"
                    else:
                        device_kind, detected_unit_id, device_info = detection
                        if device_kind == DEVICE_KIND_PAC2200:
                            gateway_model = "SENTRON PAC2200"
                        elif device_kind == DEVICE_KIND_VERSICHARGE:
                            gateway_model = (
                                str(device_info.get("model") or "").strip()
                                or "VersiCharge AC Series"
                            )
                        elif device_kind == DEVICE_KIND_POWERCENTER:
                            gateway_model = gateway_model_from_variant(
                                device_info["variant"]
                            )
                        else:
                            errors["base"] = "unsupported_device"
                            gateway_model = None

                        if gateway_model is not None:
                            _LOGGER.info(
                                "Siemens Modbus root erkannt: host=%s port=%s "
                                "device_kind=%s model=%s unit_id=%s",
                                host,
                                port,
                                device_kind,
                                gateway_model,
                                detected_unit_id,
                            )
                            return self.async_create_entry(
                                title=gateway_model,
                                data={
                                    CONF_HOST: host,
                                    CONF_PORT: port,
                                    CONF_DEVICE_KIND: device_kind,
                                    CONF_MODBUS_UNIT_ID: detected_unit_id,
                                },
                            )
            except Exception as err:  # noqa: BLE001
                _LOGGER.warning(
                    "Siemens SENTRON Gateway-Erkennung fehlgeschlagen: host=%s port=%s err=%r",
                    host,
                    port,
                    err,
                )
                errors["base"] = "cannot_connect"
            finally:
                await modbus.async_close()

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_HOST): str,
                    vol.Optional(CONF_PORT, default=DEFAULT_PORT): vol.All(
                        vol.Coerce(int), vol.Range(min=1, max=65535)
                    ),
                    # This address is only used when the root is VersiCharge.
                    vol.Optional(
                        CONF_MODBUS_UNIT_ID,
                        default=VERSICHARGE_DEFAULT_UNIT_ID,
                    ): vol.All(vol.Coerce(int), vol.Range(min=1, max=247)),
                }
            ),
            errors=errors,
        )
