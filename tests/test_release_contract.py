"""Dependency-free release-contract tests for the custom integration."""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path
import re
from types import SimpleNamespace
import unittest


ROOT = Path(__file__).resolve().parents[1]
INTEGRATION = ROOT / "custom_components" / "siemens_sentron"


def _load_entity_ids_module():
    spec = importlib.util.spec_from_file_location(
        "sentron_entity_ids",
        INTEGRATION / "entity_ids.py",
    )
    if spec is None or spec.loader is None:
        raise RuntimeError("Could not load entity_ids.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


ENTITY_IDS = _load_entity_ids_module()


class _ExampleEntity(ENTITY_IDS.SentronEntityIdMixin):
    def __init__(self, *, entry_id: str, translation_key: str, slave=None) -> None:
        self.entry = SimpleNamespace(entry_id=entry_id)
        self.translation_key = translation_key
        if slave is not None:
            self.slave = slave


class EntityIdContractTests(unittest.TestCase):
    def test_canonical_measurement_names(self) -> None:
        self.assertEqual(ENTITY_IDS.canonical_object_id("active_power"), "power_active")
        self.assertEqual(
            ENTITY_IDS.canonical_object_id("energy_active_import_collective"),
            "energy_active_import",
        )

    def test_root_and_unit_ids_are_scoped_and_collision_free(self) -> None:
        root = _ExampleEntity(entry_id="A1B2", translation_key="firmware")
        unit_1 = _ExampleEntity(
            entry_id="A1B2", translation_key="active_power", slave=1
        )
        unit_2 = _ExampleEntity(
            entry_id="A1B2", translation_key="active_power", slave=2
        )
        other_entry = _ExampleEntity(
            entry_id="C3D4", translation_key="active_power", slave=1
        )

        self.assertEqual(
            root.suggested_object_id,
            "sentron_a1b2_root_firmware_version",
        )
        self.assertEqual(
            unit_1.suggested_object_id,
            "sentron_a1b2_unit_1_power_active",
        )
        self.assertEqual(
            len(
                {
                    root.suggested_object_id,
                    unit_1.suggested_object_id,
                    unit_2.suggested_object_id,
                    other_entry.suggested_object_id,
                }
            ),
            4,
        )

    def test_all_mapped_suffixes_are_valid_object_id_parts(self) -> None:
        valid = re.compile(r"^[a-z0-9_]+$")
        for suffix in ENTITY_IDS.CANONICAL_OBJECT_IDS.values():
            self.assertRegex(suffix, valid)


class RepositoryContractTests(unittest.TestCase):
    def test_release_metadata_matches(self) -> None:
        manifest = json.loads((INTEGRATION / "manifest.json").read_text())
        hacs = json.loads((ROOT / "hacs.json").read_text())
        self.assertEqual(manifest["domain"], "siemens_sentron")
        self.assertEqual(manifest["version"], "V26.09.08")
        self.assertTrue(manifest["config_flow"])
        self.assertEqual(manifest["codeowners"], ["@powerassistant"])
        self.assertEqual(
            manifest["documentation"],
            "https://github.com/powerassistant/ha-siemens-sentron",
        )
        self.assertEqual(hacs["homeassistant"], "2026.8.0")
        self.assertEqual(manifest["requirements"], ["pymodbus==3.13.1"])

    def test_binary_sensor_platform_is_forwarded(self) -> None:
        setup_source = (INTEGRATION / "__init__.py").read_text()
        self.assertIn("Platform.BINARY_SENSOR", setup_source)
        self.assertTrue((INTEGRATION / "binary_sensor.py").is_file())

    def test_mit_license_and_disclaimer_are_present(self) -> None:
        license_text = (ROOT / "LICENSE").read_text()
        disclaimer = (ROOT / "DISCLAIMER.md").read_text()
        disclaimer_de = (ROOT / "DISCLAIMER_DE.md").read_text()
        self.assertTrue(license_text.startswith("MIT License\n"))
        self.assertIn("Copyright (c) 2026 powerassistant", license_text)
        self.assertIn('THE SOFTWARE IS PROVIDED "AS IS"', license_text)
        self.assertIn("mandatory law", disclaimer.lower())
        self.assertIn("not a protective device", disclaimer.lower())
        self.assertIn("Privatperson", disclaimer_de)
        self.assertIn("Zwingendes Recht bleibt unberührt", disclaimer_de)

    def test_existing_entity_ids_are_not_regenerated(self) -> None:
        setup_source = (INTEGRATION / "__init__.py").read_text()
        self.assertNotIn("async_regenerate_entity_id", setup_source)
        self.assertNotIn("new_entity_id=", setup_source)
        self.assertEqual(ENTITY_IDS.CONFIG_ENTRY_MINOR_VERSION, 4)

    def test_reactive_and_apparent_energy_do_not_claim_active_energy_class(self) -> None:
        pac_source = (INTEGRATION / "pac2200.py").read_text()
        self.assertIn('device_class=ENERGY if unit == "kWh" else None', pac_source)

    def test_write_entities_are_disabled_by_default(self) -> None:
        for filename in ("button.py", "number.py", "select.py"):
            source = (INTEGRATION / filename).read_text()
            self.assertIn("_attr_entity_registry_enabled_default = False", source)

        switch_source = (INTEGRATION / "switch.py").read_text()
        base_start = switch_source.index("class SentronBaseSwitchEntity")
        base_end = switch_source.index("class DeviceLocalizeSwitchEntity")
        self.assertIn(
            "_attr_entity_registry_enabled_default = False",
            switch_source[base_start:base_end],
        )

    def test_no_optimistic_command_success_text_remains(self) -> None:
        for filename in ("button.py", "switch.py"):
            source = (INTEGRATION / filename).read_text().lower()
            self.assertNotIn("continuing optimistically", source)

    def test_write_guard_and_strict_ack_contract_are_present(self) -> None:
        coordinator_source = (INTEGRATION / "coordinator.py").read_text()
        modbus_source = (INTEGRATION / "modbus_api.py").read_text()
        self.assertIn("self._write_lock = asyncio.Lock()", coordinator_source)
        self.assertGreaterEqual(
            coordinator_source.count("async with self._write_lock:"), 4
        )
        self.assertIn("if result is None:\n            return False", modbus_source)
        self.assertNotIn("for attempt in range", modbus_source)

    def test_versicharge_energy_restores_native_units(self) -> None:
        sensor_source = (INTEGRATION / "sensor.py").read_text()
        self.assertIn(
            "class VersiChargeSensorEntity(SentronBaseEntity, RestoreSensor)",
            sensor_source,
        )
        self.assertIn("async_get_last_sensor_data()", sensor_source)
        self.assertNotIn(
            "restore_versicharge_energy(float(last_state.state))",
            sensor_source,
        )

    def test_versicharge_phase_mode_has_no_write_path(self) -> None:
        runtime_source = "\n".join(
            path.read_text() for path in INTEGRATION.glob("*.py")
        )
        self.assertNotIn("write_versicharge_phase", runtime_source)
        self.assertNotIn("VersiChargePhaseSelect", runtime_source)

    def test_versicharge_power_input_is_single_stable_kw_control(self) -> None:
        number_source = (INTEGRATION / "number.py").read_text()
        target_base_start = number_source.index("class VersiChargeTargetNumberEntity")
        block_start = number_source.index("class VersiChargeChargingPowerNumber")
        block_end = number_source.index(
            "class VersiChargeFallbackCurrentNumber", block_start
        )
        target_base = number_source[target_base_start:block_start]
        power_number = number_source[block_start:block_end]

        self.assertIn("UnitOfPower.KILO_WATT", power_number)
        self.assertIn("_attr_native_step = 0.1", power_number)
        self.assertIn("def _handle_coordinator_update", target_base)
        self.assertIn("_last_presentation_signature", target_base)
        self.assertIn("nominal_power_bounds_kw", power_number)
        self.assertNotIn("VersiChargeChargingCurrentNumber", number_source)
        self.assertNotIn('"actual_power_w"', power_number)
        self.assertNotIn('"charging_enabled"', power_number)
        self.assertNotIn("power_factor", power_number)

        coordinator_source = (INTEGRATION / "coordinator.py").read_text()
        self.assertIn("whole_amp_current_for_power_kw", coordinator_source)
        self.assertIn("_versicharge_command_in_progress", coordinator_source)
        self.assertIn("no command was queued", coordinator_source)
        self.assertIn("it was not retried", coordinator_source)
        self.assertNotIn("_versicharge_target_mode", coordinator_source)
        self.assertNotIn("VERSICHARGE_WRITE_READBACK_DELAY_SECONDS", coordinator_source)
        self.assertNotIn("charging_current_readback_matches", coordinator_source)
        self.assertNotIn("retained_measured_phase_count", coordinator_source)
        capability_start = coordinator_source.index(
            "def versicharge_current_control_available"
        )
        capability_end = coordinator_source.index(
            "def _require_versicharge_current_control_available",
            capability_start,
        )
        self.assertNotIn(
            'get("charging_current_limit")',
            coordinator_source[capability_start:capability_end],
        )

        update_start = coordinator_source.index("async def _async_update_data")
        update_end = coordinator_source.index(
            "async def _async_read_gateway_values", update_start
        )
        versicharge_update = coordinator_source[update_start:update_end]
        self.assertNotIn("async with self._write_lock", versicharge_update)
        self.assertNotIn("async_read_versicharge_static", versicharge_update)

        versicharge_source = (INTEGRATION / "versicharge.py").read_text()
        phase_start = versicharge_source.index("def active_phase_count")
        phase_end = versicharge_source.index("def power_per_amp", phase_start)
        self.assertNotIn("current_l", versicharge_source[phase_start:phase_end])

        switch_source = (INTEGRATION / "switch.py").read_text()
        self.assertIn("return self.coordinator.versicharge_enabled_state", switch_source)

    def test_current_device_hierarchy_api_is_used(self) -> None:
        runtime_source = "\n".join(
            path.read_text()
            for path in INTEGRATION.glob("*.py")
        )
        self.assertIn("via_device_id=", runtime_source)
        self.assertNotIn("via_device=(", runtime_source)


if __name__ == "__main__":
    unittest.main()
