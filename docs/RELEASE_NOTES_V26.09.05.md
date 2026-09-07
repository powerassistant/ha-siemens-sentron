# Release notes V26.09.05

Release date: 2026-09-05

## Headline

This release adds Siemens VersiCharge AC Gen3 as a standalone root device to
the existing SENTRON integration. It combines local charging monitoring,
Home Assistant Energy Dashboard support and guarded PV-surplus controls in one
config entry.

## VersiCharge monitoring

- Auto-detection at configurable Modbus unit ID `2`, with automatic fallback
  to unit ID `1` when the default is used.
- Five-second live polling with a 15-second Modbus timeout.
- Cumulative charging energy (`kWh`, total increasing) and actual active power
  (`W`, measurement).
- Per-phase current, voltage, active/apparent/reactive power and power factor.
- EVSE/OCPP state, fault code, vehicle connected, charging and problem signals.
- Installation current, phase mode, temperature, meter, firmware, outlet,
  connectivity and register-map diagnostics.
- Filtering for isolated cumulative-energy counter drops.

## Firmware compatibility

The integration distinguishes the attached legacy `09/2023` map from the
current Siemens `02/2025` map through the A8 firmware.

- Below firmware `2.135`: total energy uses `0.1 Wh` units, power factor uses a
  `0.01` scale and charging current is commanded in whole amperes.
- Firmware `2.135` and newer: total energy uses `1 Wh` units, power factor uses
  a `0.001` scale and current writes can represent hundredths of an ampere.
  Home Assistant exposes a practical `0.1 A` step while readback remains whole
  amperes.
- Firmware `2.136` changes the EVSE state and error-code model; modern decoding
  is applied accordingly.

Unknown firmware uses current-map measurement scaling but conservative,
cross-firmware whole-ampere commands unless a newer-only extension block
positively identifies the modern profile.

## PV-surplus controls

New controls are disabled by default:

- pause/resume switch;
- direct charging-current target;
- virtual charging-power target in watts;
- native fallback current and timeout.

The virtual watt target converts active power to amperes using the reported
one-/three-phase mode plus measured phase-to-neutral voltage and power factor:

\[
I = P / \sum(U_{pN} \cdot PF_p)
\]

At `230 V`, `PF=1` and the `6 A` charging floor, the minimum is approximately
`1.38 kW` single-phase or `4.14 kW` three-phase. Modern `0.1 A` target steps
correspond to about `23 W` single-phase or `69 W` three-phase under the same
conditions; actual vehicle behavior and whole-ampere readback can be coarser.

See [VersiCharge monitoring and PV-surplus control](VERSICHARGE.md) for the
Home Assistant automation example. It correctly calculates available charging
power as:

`current measured charging power + grid export - export reserve`

This avoids the common error of applying only residual grid export after the
charger is already running.

## Important phase and fallback behavior

- Phase mode is observation-only. Siemens marks the register read-only on
  firmware `2.135` and newer, so this release does not perform automatic
  1/3-phase switching.
- For PV-only operation, fallback current `0 A` and fallback time `60 s` are a
  conservative recommendation. Fallback values are not persistent and must be
  checked after a charger restart or power cycle.
- OCPP or cloud policies can override or clamp Modbus commands. Use actual
  active power as feedback rather than trusting the requested target.
- The pause/resume target is kept only while the config entry remains loaded.
  After a Home Assistant restart, resuming without first setting a new target
  uses the conservative `6 A` default.

## Validation status

The repository contains software tests for register decoding, firmware scaling,
current/power conversion, energy filtering and integration contracts. These
checks do not constitute physical hardware validation.

Before production use, validate the charger firmware, one-/three-phase wiring,
installation-current limit, control readback, communication-loss fallback and
OCPP interaction on a non-critical charging session.

## Upgrade

Existing config entries and customized entity IDs remain unchanged. After
installing the release and restarting Home Assistant, add a separate config
entry for each standalone VersiCharge host. New write-capable entities remain
disabled until enabled deliberately in the entity registry.
