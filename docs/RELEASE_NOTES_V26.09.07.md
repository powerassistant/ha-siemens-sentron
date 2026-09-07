# Release notes V26.09.07

Release date: 2026-09-06

## VersiCharge current-readback hotfix

This hotfix aligns command verification with the charger firmware's coarse
register `1633` readback. A confirmed modern charger accepts current commands
in `0.01 A` resolution but may return only an adjacent whole-ampere value. The
observed `14.49 A` command followed by `15 A` is therefore accepted after the
positive Modbus write acknowledgement instead of being reported as a failed
service call. Modern fractional commands are verified against the charger's
observed round-up behavior; incompatible replies still fail verification.

The decoder also tolerates a modern charger echoing the centiampere register
representation and exposes the original raw value as a diagnostic attribute.

## Stable target controls

Charging-current and charging-power inputs no longer disappear when the
isolated register `1633` read is missing during an otherwise successful poll.
Measurements and readback freshness remain diagnostic data; they no longer
control whether the target input itself is shown.

When Home Assistant starts while the charger is paused or its current-limit
readback is temporarily unknown, the integration uses a safe `6 A` resume
target and calculates the corresponding Watt value as soon as the phase mode
is known. Editing this target does not start a paused charger; the separate
charging switch remains the explicit start/stop command.

Both target controls suppress telemetry-only state redraws, so a five-second
poll cannot erase a value while it is being typed. Whole-Watt input remains
available throughout stable, phase-specific nominal-230-V bounds. Live voltage
and power factor still determine the current conversion.

Before a Watt-based target is resumed, its current is recalculated for the
currently detected phase mode. A target outside a changed phase range is
rejected until it is updated, preventing an old single-phase current from being
reused unchanged for a three-phase session.

## Upgrade

Install `V26.09.07` and restart Home Assistant completely. Existing config
entries and entity IDs remain unchanged.
