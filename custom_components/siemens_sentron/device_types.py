"""Central device type classification for Siemens SENTRON.

Root devices and datasets stay separated:
- Powercenter gateways: onboarding/discovery host attached end devices.
- Powercenter end devices: gateway slot discovery plus end-device profiles.
- PAC2200: standalone root device with its own onboarding and dataset.
- VersiCharge: standalone EV charger root with its own Modbus dataset.
"""

from __future__ import annotations

DEVICE_KIND_POWERCENTER = "powercenter"
DEVICE_KIND_PAC2200 = "pac2200"
DEVICE_KIND_VERSICHARGE = "versicharge"
DEVICE_KIND_END_DEVICE = "end_device"

POWERCENTER_1000 = "powercenter_1000"
POWERCENTER_1100 = "powercenter_1100"
POWERCENTER_2000 = "powercenter_2000"

POWERCENTER_VARIANT_TO_TYPE = {
    14: POWERCENTER_1100,
    16: POWERCENTER_2000,
}


def powercenter_type_from_variant(variant: int | None) -> str:
    """Return the normalized Powercenter type for a gateway variant."""
    return POWERCENTER_VARIANT_TO_TYPE.get(variant, POWERCENTER_1000)


def is_pac2200_root(device: dict | None) -> bool:
    """Return True for a directly connected PAC2200 root device."""
    return bool(device and device.get("device_kind") == DEVICE_KIND_PAC2200)


def is_versicharge_root(device: dict | None) -> bool:
    """Return True for a directly connected VersiCharge root device."""
    return bool(device and device.get("device_kind") == DEVICE_KIND_VERSICHARGE)


def is_powercenter_root(device: dict | None) -> bool:
    """Return True for a Powercenter gateway root device."""
    return bool(device and device.get("device_kind") == DEVICE_KIND_POWERCENTER)


def is_powercenter_1000(device: dict | None) -> bool:
    return bool(device and device.get("powercenter_type") == POWERCENTER_1000)


def is_powercenter_1100_or_2000(device: dict | None) -> bool:
    """Return True for Powercenter generations using the 1100/2000 slot maps."""
    if not device:
        return False
    if device.get("powercenter_type") in {POWERCENTER_1100, POWERCENTER_2000}:
        return True
    variant = device.get("variant")
    model = str(device.get("model", ""))
    return variant in (14, 16) or "1100" in model or "2000" in model
