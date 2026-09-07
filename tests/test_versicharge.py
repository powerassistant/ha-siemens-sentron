"""Dependency-free tests for the Siemens VersiCharge register model."""

from __future__ import annotations

import asyncio
import importlib.util
from pathlib import Path
import sys
import unittest


ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = ROOT / "custom_components" / "siemens_sentron" / "versicharge.py"


spec = importlib.util.spec_from_file_location("sentron_versicharge", MODULE_PATH)
if spec is None or spec.loader is None:
    raise RuntimeError("Could not load versicharge.py")
VERSICHARGE = importlib.util.module_from_spec(spec)
# dataclasses resolves annotations through sys.modules while decorating classes.
sys.modules[spec.name] = VERSICHARGE
spec.loader.exec_module(VERSICHARGE)


def _dynamic_blocks(
    *,
    state: int = 0x4331,  # "C1"
    error: int = 0,
    ocpp: int = 3,
    current_limit: int = 16,
    phase_powers: tuple[int, int, int] = (0, 0, 0),
    reported_power: int = 0,
    power_factors: tuple[int, int, int, int] = (1000, 1000, 1000, 1000),
    energy: int = 100_000,
) -> dict[int, list[int]]:
    """Build current-map blocks without reading undocumented gaps."""
    power_block = [0, 60]
    power_block.extend(phase_powers)
    power_block.append(reported_power)
    power_block.extend(power_factors)
    power_block.extend([0] * 8)
    return {
        1599: [state, error, ocpp, 25, 26, 27, 28],
        1633: [current_limit],
        1640: [0, 0, 1],
        1647: [10, 10, 10, 30, 230, 231, 229, 400, 399, 401],
        1660: power_block,
        1692: [(energy >> 16) & 0xFFFF, energy & 0xFFFF],
    }


class VersiChargeDecodeTests(unittest.TestCase):
    def test_firmware_tuple_preserves_build_components(self) -> None:
        self.assertEqual(
            VERSICHARGE.firmware_tuple("2.500.34+25-32"),
            (2, 500, 34),
        )
        self.assertEqual(VERSICHARGE.register_profile("2.500.34+25-32"), "modern")

    def test_modern_energy_and_power_factor_scaling(self) -> None:
        values = VERSICHARGE.decode_dynamic_values(
            _dynamic_blocks(power_factors=(995, 981, 1000, 992)),
            profile="modern",
        )
        self.assertEqual(values["energy_total"], 100.0)
        self.assertEqual(values["power_factor_l1"], 0.995)
        self.assertEqual(values["power_factor_l2"], 0.981)
        self.assertEqual(values["power_factor_average"], 0.992)

    def test_current_limit_accepts_whole_amp_and_centiamp_readbacks(self) -> None:
        whole = VERSICHARGE.decode_dynamic_values(
            _dynamic_blocks(current_limit=15), profile="modern"
        )
        self.assertEqual(whole["charging_current_limit_raw"], 15)
        self.assertEqual(whole["charging_current_limit"], 15.0)

        echoed = VERSICHARGE.decode_dynamic_values(
            _dynamic_blocks(current_limit=1449), profile="modern"
        )
        self.assertEqual(echoed["charging_current_limit_raw"], 1449)
        self.assertEqual(echoed["charging_current_limit"], 14.49)

        invalid = VERSICHARGE.decode_dynamic_values(
            _dynamic_blocks(current_limit=9000), profile="modern"
        )
        self.assertIsNone(invalid["charging_current_limit"])

        self.assertEqual(
            VERSICHARGE.normalize_charging_current_readback(0, profile="modern"),
            0.0,
        )
        self.assertEqual(
            VERSICHARGE.normalize_charging_current_readback(80, profile="modern"),
            80.0,
        )
        for raw in (81, 100, 8001):
            self.assertIsNone(
                VERSICHARGE.normalize_charging_current_readback(
                    raw, profile="modern"
                )
            )
        self.assertEqual(
            VERSICHARGE.normalize_charging_current_readback(
                101, profile="modern"
            ),
            1.01,
        )
        self.assertEqual(
            VERSICHARGE.normalize_charging_current_readback(
                8000, profile="modern"
            ),
            80.0,
        )
        self.assertIsNone(
            VERSICHARGE.normalize_charging_current_readback(
                701, profile="legacy"
            )
        )

        missing_blocks = _dynamic_blocks()
        missing_blocks.pop(1633)
        missing = VERSICHARGE.decode_dynamic_values(
            missing_blocks, profile="modern"
        )
        self.assertIsNone(missing["charging_current_limit_raw"])
        self.assertIsNone(missing["charging_current_limit"])

    def test_legacy_energy_and_power_factor_scaling(self) -> None:
        values = VERSICHARGE.decode_dynamic_values(
            _dynamic_blocks(power_factors=(99, 98, 100, 99)),
            profile="legacy",
        )
        self.assertEqual(values["energy_total"], 10.0)
        self.assertEqual(values["power_factor_l1"], 0.99)
        self.assertEqual(values["power_factor_l2"], 0.98)
        self.assertEqual(values["power_factor_average"], 0.99)
        fine_energy = VERSICHARGE.decode_dynamic_values(
            _dynamic_blocks(energy=1),
            profile="legacy",
        )
        self.assertEqual(fine_energy["energy_total"], 0.0001)

    def test_all_ones_sentinels_are_unavailable(self) -> None:
        self.assertIsNone(VERSICHARGE.decode_uint16(0xFFFF))
        self.assertIsNone(VERSICHARGE.decode_int16(0xFFFF))
        self.assertIsNone(VERSICHARGE.decode_uint32_be([0xFFFF, 0xFFFF]))

        values = VERSICHARGE.decode_dynamic_values(
            _dynamic_blocks(power_factors=(0xFFFF,) * 4, energy=0xFFFFFFFF),
            profile="modern",
        )
        self.assertIsNone(values["energy_total"])
        self.assertIsNone(values["power_factor_l1"])

    def test_signed_phase_power_does_not_create_65_kw_spike(self) -> None:
        self.assertEqual(VERSICHARGE.decode_int16(0xFFE4), -28)
        values = VERSICHARGE.decode_dynamic_values(
            _dynamic_blocks(
                phase_powers=(0xFFE4, 100, 0),
                reported_power=0xFFE4,
            ),
            profile="modern",
        )
        self.assertEqual(values["active_power_l1"], -28)
        self.assertEqual(values["active_power_total_reported"], -28)
        self.assertEqual(values["active_power_total"], 72)
        self.assertLess(values["active_power_total"], 65_000)

    def test_reactive_power_phase_sum_uses_documented_uint16(self) -> None:
        blocks = _dynamic_blocks()
        blocks[1660][17] = 40_000
        values = VERSICHARGE.decode_dynamic_values(blocks, profile="modern")
        self.assertEqual(values["reactive_power_total"], 40_000)

    def test_modern_evse_ocpp_and_error_mapping(self) -> None:
        values = VERSICHARGE.decode_dynamic_values(
            _dynamic_blocks(state=0x4520, error=46, ocpp=5),
            profile="modern",
        )
        self.assertEqual(values["evse_state"], "recoverable_fault")
        self.assertEqual(values["ocpp_state"], "suspended_evse")
        self.assertEqual(values["error"], "ground_monitoring_fault")
        self.assertTrue(values["error_recoverable"])

        nonrecoverable = VERSICHARGE.decode_dynamic_values(
            _dynamic_blocks(state=0x4620, error=48, ocpp=6),
            profile="modern",
        )
        self.assertEqual(nonrecoverable["evse_state"], "non_recoverable_fault")
        self.assertEqual(nonrecoverable["ocpp_state"], "faulted")
        self.assertEqual(nonrecoverable["error"], "over_current_fault")
        self.assertFalse(nonrecoverable["error_recoverable"])

    def test_unknown_enum_values_use_declared_unknown_state(self) -> None:
        values = VERSICHARGE.decode_dynamic_values(
            _dynamic_blocks(error=999, ocpp=999),
            profile="modern",
        )
        self.assertEqual(values["ocpp_state"], "unknown")
        self.assertEqual(values["error"], "unknown")

        phase_blocks = _dynamic_blocks()
        phase_blocks[1640][2] = 99
        values = VERSICHARGE.decode_dynamic_values(
            phase_blocks,
            profile="modern",
        )
        self.assertEqual(values["charger_phase"], "unknown")

    def test_energy_dashboard_sensor_metadata(self) -> None:
        descriptions = {
            item.key: item for item in VERSICHARGE.VERSICHARGE_SENSORS
        }
        energy = descriptions["energy_total"]
        self.assertEqual(energy.unit, "kWh")
        self.assertEqual(energy.device_class, "energy")
        self.assertEqual(energy.state_class, "total_increasing")

        power = descriptions["active_power_total"]
        self.assertEqual(power.unit, "W")
        self.assertEqual(power.device_class, "power")
        self.assertEqual(power.state_class, "measurement")

        for key in (
            "evse_state",
            "ocpp_state",
            "error",
            "charger_phase",
            "platform_type",
            "outlet_type",
            "delay_setting",
            "connectivity",
            "meter_type",
        ):
            self.assertIn("unknown", descriptions[key].options or ())

    def test_complete_static_timeout_does_not_create_assumed_profile(self) -> None:
        class NoReplyReader:
            async def read_holding_registers(
                self, slave: int, address: int, count: int
            ) -> None:
                return None

        values = asyncio.run(
            VERSICHARGE.async_read_versicharge_static(NoReplyReader(), 2)
        )
        self.assertEqual(values, {})


class VersiChargeControlMathTests(unittest.TestCase):
    def test_current_encoding_is_whole_ampere_for_all_maps(self) -> None:
        self.assertEqual(VERSICHARGE.encode_charging_current(0), 0)
        self.assertEqual(VERSICHARGE.encode_charging_current(6), 6)
        self.assertEqual(VERSICHARGE.encode_charging_current(16), 16)
        with self.assertRaisesRegex(ValueError, "whole amperes"):
            VERSICHARGE.encode_charging_current(8.7)

    def test_power_input_quantizes_half_up_to_one_decimal_kw(self) -> None:
        self.assertEqual(VERSICHARGE.quantize_power_kw(2.44), 2.4)
        self.assertEqual(VERSICHARGE.quantize_power_kw(2.45), 2.5)
        self.assertEqual(VERSICHARGE.quantize_power_kw("2.5"), 2.5)
        with self.assertRaisesRegex(ValueError, "charging switch"):
            VERSICHARGE.quantize_power_kw(0)

    def test_single_phase_target_is_nominal_and_ignores_live_measurements(self) -> None:
        values = {
            "effective_phase_count": 1,
            "voltage_l1_n": 225,
            "power_factor_l1": 0.96,
        }
        self.assertEqual(VERSICHARGE.active_phase_count(values), 1)
        self.assertAlmostEqual(VERSICHARGE.power_per_amp(values, 1), 216.0)
        self.assertAlmostEqual(VERSICHARGE.power_for_current(6, values), 1296.0)
        self.assertEqual(
            VERSICHARGE.whole_amp_current_for_power_kw(2.5, values, 16),
            11,
        )
        values["voltage_l1_n"] = 245
        values["power_factor_l1"] = 0.82
        self.assertEqual(
            VERSICHARGE.whole_amp_current_for_power_kw(2.5, values, 16), 11
        )
        self.assertEqual(VERSICHARGE.nominal_power_bounds_kw(values, 16), (1.4, 3.7))

    def test_three_phase_target_rounds_to_whole_ampere(self) -> None:
        values = {
            "effective_phase_count": 3,
            "voltage_l1_n": 230,
            "voltage_l2_n": 232,
            "voltage_l3_n": 228,
            "power_factor_l1": 0.98,
            "power_factor_l2": 0.97,
            "power_factor_l3": 0.99,
        }
        watts_per_amp = 230 * 0.98 + 232 * 0.97 + 228 * 0.99
        self.assertEqual(VERSICHARGE.active_phase_count(values), 3)
        self.assertAlmostEqual(VERSICHARGE.power_per_amp(values, 3), watts_per_amp)
        # IEC charging starts at 6 A per active phase: about 4.06 kW here.
        self.assertAlmostEqual(
            VERSICHARGE.power_for_current(6, values), watts_per_amp * 6
        )
        self.assertGreater(VERSICHARGE.power_for_current(6, values), 2_000)
        self.assertEqual(
            VERSICHARGE.whole_amp_current_for_power_kw(6.9, values, 16),
            10,
        )
        self.assertEqual(
            VERSICHARGE.nominal_power_bounds_kw(values, 16),
            (4.1, 11.0),
        )
        self.assertEqual(VERSICHARGE.nominal_power_kw_for_current(11, 3), 7.6)

    def test_nominal_power_bounds_are_stable_and_enforced(self) -> None:
        one_phase = {
            "effective_phase_count": 1,
            "voltage_l1_n": 245,
            "power_factor_l1": 0.82,
        }
        self.assertEqual(
            VERSICHARGE.nominal_power_bounds_kw(one_phase, 16),
            (1.4, 3.7),
        )
        self.assertIsNone(VERSICHARGE.nominal_power_bounds_kw({}, 16))
        with self.assertRaisesRegex(ValueError, "1.4..3.7 kW"):
            VERSICHARGE.whole_amp_current_for_power_kw(4.0, one_phase, 16)

    def test_power_conversion_refuses_to_guess_unknown_phase_mode(self) -> None:
        values = {
            "voltage_l1_n": 230,
            "voltage_l2_n": 230,
            "voltage_l3_n": 230,
        }
        self.assertIsNone(VERSICHARGE.active_phase_count(values))
        self.assertIsNone(VERSICHARGE.power_for_current(6, values))
        with self.assertRaisesRegex(ValueError, "phase mode"):
            VERSICHARGE.whole_amp_current_for_power_kw(2.0, values, 16)

    def test_phase_count_uses_charger_type_not_transient_current_samples(self) -> None:
        three_phase_charger = {
            "charger_phase_raw": 1,
            "current_l1": 10,
            "current_l2": 0,
            "current_l3": 0,
        }
        self.assertEqual(VERSICHARGE.active_phase_count(three_phase_charger), 3)

        one_phase_charger = {
            "charger_phase_raw": 0,
            "current_l1": 10,
            "current_l2": 10,
            "current_l3": 10,
        }
        self.assertEqual(VERSICHARGE.active_phase_count(one_phase_charger), 1)


class TotalEnergyFilterTests(unittest.TestCase):
    def test_isolated_lower_values_are_suppressed(self) -> None:
        energy = VERSICHARGE.TotalEnergyFilter(confirmations=3)
        self.assertEqual(energy.update(100.0), 100.0)
        self.assertEqual(energy.update(101.0), 101.0)
        # Repeated placeholder zeroes are never mistaken for a real reset.
        for _ in range(5):
            self.assertEqual(energy.update(0.0), 101.0)
        self.assertEqual(energy.update(102.0), 102.0)

    def test_confirmed_reset_is_accepted_and_none_does_not_reset_state(self) -> None:
        energy = VERSICHARGE.TotalEnergyFilter(confirmations=3)
        self.assertEqual(energy.update(100.0), 100.0)
        self.assertEqual(energy.update(None), 100.0)
        self.assertEqual(energy.update(1.0), 100.0)
        self.assertEqual(energy.update(1.1), 100.0)
        self.assertEqual(energy.update(1.2), 1.2)
        self.assertEqual(energy.update(1.3), 1.3)

    def test_restored_energy_seeds_guard_after_reload(self) -> None:
        energy = VERSICHARGE.TotalEnergyFilter(confirmations=3)
        # A transient initial zero can arrive before the entity has restored
        # its last recorder state during platform setup.
        self.assertEqual(energy.update(0.0), 0.0)
        energy.seed(100.0)
        self.assertEqual(energy.update(0.0), 100.0)
        self.assertEqual(energy.update(1.0), 100.0)
        self.assertEqual(energy.update(1.1), 1.1)


if __name__ == "__main__":
    unittest.main()
