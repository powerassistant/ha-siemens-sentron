#!/usr/bin/env python3
"""Import every runtime module against the pinned dependency set."""

from __future__ import annotations

import importlib
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


MODULES = (
    "__init__",
    "binary_sensor",
    "button",
    "config_flow",
    "const",
    "coordinator",
    "device_types",
    "discovery",
    "diagnostics",
    "entity_ids",
    "gateway",
    "modbus_api",
    "number",
    "pac2200",
    "profiles",
    "select",
    "sensor",
    "switch",
    "versicharge",
)


for module in MODULES:
    importlib.import_module(f"custom_components.siemens_sentron.{module}")

print(f"Imported {len(MODULES)} Siemens SENTRON runtime modules.")
