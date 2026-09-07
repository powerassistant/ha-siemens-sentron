# Release notes V26.09.06

Release date: 2026-09-06

## Stable charging-power input

This bugfix release prevents the VersiCharge five-second telemetry refresh from
redrawing the editable charging-power field while a value is being typed.
Volatile actual-power measurements remain available through the dedicated
sensor but no longer form part of the Number entity's state updates.

## Whole-Watt targets

The virtual charging-power control now accepts every whole-Watt value between
its displayed dynamic minimum and maximum. On confirmed modern firmware, each
request is converted with the charger's `0.01 A` command resolution. The exact
requested Watt value remains visible in Home Assistant; the effective physical
power can still differ because voltage, power factor, phase count, charger and
vehicle behavior determine the result.

Legacy firmware remains limited to whole-ampere commands. The direct charging-
current control keeps its practical `0.1 A` UI step on modern firmware.

## Upgrade

Install `V26.09.06`, restart Home Assistant and reload the VersiCharge device
page. Existing config entries and entity IDs remain unchanged.
