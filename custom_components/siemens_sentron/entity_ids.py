"""Stable, language-independent entity object IDs for Siemens SENTRON."""

from __future__ import annotations


# Config-entry minor version 1.4 introduces collision-free default entity IDs
# without renaming any existing (possibly user-customized) registry entries.
CONFIG_ENTRY_MINOR_VERSION = 4
ENTITY_ID_MIGRATION_PENDING = "_sentron_entity_id_migration_pending"


# Only keys whose canonical English object ID differs from their translation
# key need to be listed.  All other translation keys already use stable,
# technical English snake_case.  The mapping deliberately describes the data
# point only; ``SentronEntityIdMixin`` adds the stable entry/device scope.
CANONICAL_OBJECT_IDS: dict[str, str] = {
    # Electrical measurements shared by single- and multi-pole devices.
    "active_power": "power_active",
    "power_active_collective": "power_active",
    "apparent_power": "power_apparent",
    "power_apparent_collective": "power_apparent",
    "reactive_power": "power_reactive",
    "power_reactive_q1_collective": "power_reactive_q1",
    "power_factor_collective": "power_factor",
    "energy_import": "energy_active_import",
    "energy_export": "energy_active_export",
    "current_average": "current",
    "current_neutral": "current_n",
    "voltage_average_ph_n": "voltage_l_n",
    "voltage_average_ph_ph": "voltage_l_l",
    "voltage_ph_n_l1": "voltage_l1_n",
    "voltage_ph_n_l2": "voltage_l2_n",
    "voltage_ph_n_l3": "voltage_l3_n",
    "voltage_ph_ph_l1_l2": "voltage_l1_l2",
    "voltage_ph_ph_l2_l3": "voltage_l2_l3",
    "voltage_ph_ph_l3_l1": "voltage_l3_l1",
    "average_temperature": "temperature_average",

    # VersiCharge measurements and controls use the same canonical electrical
    # vocabulary as the SENTRON meter families while retaining unique IDs.
    "versicharge_energy_total": "energy_active_import",
    "versicharge_active_power_total": "power_active",
    "versicharge_active_power_total_reported": "power_active_reported",
    "versicharge_active_power_l1": "power_active_l1",
    "versicharge_active_power_l2": "power_active_l2",
    "versicharge_active_power_l3": "power_active_l3",
    "versicharge_apparent_power_l1": "power_apparent_l1",
    "versicharge_apparent_power_l2": "power_apparent_l2",
    "versicharge_apparent_power_l3": "power_apparent_l3",
    "versicharge_apparent_power_total": "power_apparent",
    "versicharge_reactive_power_l1": "power_reactive_l1",
    "versicharge_reactive_power_l2": "power_reactive_l2",
    "versicharge_reactive_power_l3": "power_reactive_l3",
    "versicharge_reactive_power_total": "power_reactive",
    "versicharge_power_factor_l1": "power_factor_l1",
    "versicharge_power_factor_l2": "power_factor_l2",
    "versicharge_power_factor_l3": "power_factor_l3",
    "versicharge_power_factor_average": "power_factor",
    "versicharge_current_l1": "current_l1",
    "versicharge_current_l2": "current_l2",
    "versicharge_current_l3": "current_l3",
    "versicharge_current_phase_sum": "current_phase_sum",
    "versicharge_voltage_l1_n": "voltage_l1_n",
    "versicharge_voltage_l2_n": "voltage_l2_n",
    "versicharge_voltage_l3_n": "voltage_l3_n",
    "versicharge_voltage_l1_l2": "voltage_l1_l2",
    "versicharge_voltage_l2_l3": "voltage_l2_l3",
    "versicharge_voltage_l3_l1": "voltage_l3_l1",
    "versicharge_charging_current": "charging_current",
    "versicharge_charging_current_limit": "charging_current_limit",
    "versicharge_charging_power": "charging_power",
    "versicharge_minimum_charging_power": "charging_power_minimum",
    "versicharge_maximum_charging_power": "charging_power_maximum",
    "versicharge_charger_phase": "phase_mode",
    "versicharge_effective_phase_count": "phase_count",
    "versicharge_fallback_current": "fallback_current",
    "versicharge_fallback_time": "fallback_time",
    "versicharge_modbus_unit_id": "unit_id",
    "versicharge_vehicle_connected": "vehicle_connected",
    "versicharge_charging": "charging",
    "versicharge_problem": "problem",
    "versicharge_charging_enabled": "charging_enabled",

    # RCM, state and I/O terminology shared across device families.
    "rcm_ac_basic_frequency": "rcm_ac_fundamental",
    "leakage": "rcm_rms_low_pass_channel_1",
    "rca_handle_state": "breaker_handle_state",
    "dido_input_1": "digital_input_1",
    "dido_input_2": "digital_input_2",
    "state_binary_inputs": "digital_input_1",
    "state_binary_outputs": "digital_output_1",
    "output_1_forcing": "output_1_forcing_source",
    "output_2_forcing": "output_2_forcing_source",
    "alarm_trip_active": "breaker_trip_active",
    "alarm_rcm_active": "rcm_alarm_active",

    # Identification and diagnostics.
    "firmware": "firmware_version",
    "variant": "device_variant",
    "order_id": "article_number",
    "discovered_devices": "discovered_device_count",
    "operating_hours_overall": "operating_hours",
    "date_time": "device_time",
    "actual_tariff": "tariff_active",
    "ble_signal_strength_rssi": "signal_strength_ble",
    "radio_signal_strength_rssi": "signal_strength_radio",
    "powercenter_write_cooldown": "write_cooldown",
    "last_state_rcd_test": "rcd_test_last_result",
    "device_test_status": "self_rcd_test_status",
    "device_test_timestamp": "self_rcd_test_timestamp",
    "unlock_acknowledge": "unlock_confirmation_time_remaining",

    # Controls and configuration.
    "locate_device": "identify",
    "switch_standby": "breaker_electronic_on_standby",
    "rca_handle": "breaker_handle",
    "output_force_1": "output_1_force",
    "output_force_2": "output_2_force",
    "start_rcm_test": "rcm_test_start",
    "start_self_rcd_test": "self_rcd_test_start",
    "reset_manual_off": "breaker_manual_off_reset",
    "unpair_device": "permanent_disconnect",
    "remote_control_communication": "remote_control_source",
    "ecpd_nominal_current": "current_nominal",
    "ecpd_instantaneous_trip_behaviour": "trip_behaviour_instantaneous",
    "ecpd_time_delay_release_behaviour": "trip_behaviour_time_delay",
    "ecpd_residual_current_trip_behaviour": "trip_behaviour_residual_current",
    "ecpd_rcd_sensitivity": "rcd_sensitivity",
    "ecpd_rcd_tripping_time": "rcd_tripping_time",
}


def canonical_object_id(translation_key: str) -> str:
    """Return the stable English object ID for an entity translation key."""
    if translation_key.startswith("energy_") and translation_key.endswith("_collective"):
        return translation_key.removesuffix("_collective")
    return CANONICAL_OBJECT_IDS.get(translation_key, translation_key)


class SentronEntityIdMixin:
    """Provide a collision-free English object ID for newly created entities."""

    @property
    def suggested_object_id(self) -> str | None:
        """Return a deterministic object ID scoped to this device and entry.

        Home Assistant treats ``suggested_object_id`` as the complete object-ID
        base and does not prepend the device name.  Including the config-entry
        and root/unit token prevents order-dependent ``_2`` suffixes when the
        same data point exists on multiple SENTRON devices.
        """
        translation_key = self.translation_key
        if translation_key is None:
            return None
        entry_token = self.entry.entry_id.lower()
        slave = getattr(self, "slave", None)
        device_token = "root" if slave is None else f"unit_{slave}"
        return (
            f"sentron_{entry_token}_{device_token}_"
            f"{canonical_object_id(translation_key)}"
        )
