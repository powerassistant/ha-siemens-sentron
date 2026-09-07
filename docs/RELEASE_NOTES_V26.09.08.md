# Release notes V26.09.08

Release date: 2026-09-07

## VersiCharge load-safety redesign

This release replaces the V26.09.07 charging-target path after a system-load
review. The audit found no internal CPU loop, listener recursion or automatic
poll-to-write feedback. It did find a real workload-amplification path: every
rapid power-target service call could wait on the same lock while earlier calls
performed a Modbus write, slept for two seconds and read register `1633` back.
With slow or missing Modbus replies, this could create an unbounded collection
of waiting Home Assistant service tasks. It is a plausible contributor to a
reported Home Assistant outage, but the available logs do not prove it was the
sole cause.

The risky path has been removed:

- a running VersiCharge command rejects a concurrent call immediately; nothing
  is added to a command queue;
- the write is attempted exactly once and is never retried automatically;
- a positive FC06 acknowledgement is required;
- the two-second sleep and immediate readback are gone;
- the normal read-only polling cycle later reports the independent register
  value;
- polling never takes the command guard and cannot be delayed behind a backlog
  of charging targets;
- physical power-target writes and resume starts have a five-second
  start-to-start limit; pause and fallback may bypass that interval but still
  fail fast while another command is active;
- local-only target changes use a separate limiter, so they cannot create a
  listener-update flood or delay an immediate resume;
- every write has a twelve-second outer deadline;
- normal polling is reduced from five to ten seconds and the VersiCharge
  request timeout from fifteen to five seconds;
- immutable identification data is read during discovery, not periodically.

## One simple kW target

There is now one user-facing charge target: **Charging power target** in `kW`
with a `0.1 kW` step. The direct **Charging current target** writer has been
removed. The charger current-limit sensor remains read-only and the separate
**Charging enabled** switch still pauses or resumes charging.

Every accepted power value is converted once:

\[
I = \operatorname{round\_half\_up}
\left(\frac{P_{kW}\times1000}{230\times n_{phases}}\right)
\]

The resulting whole ampere is written directly to Modbus offset `1633`. The
phase count comes only from the stable charger type reported by read-only
register `1642`; transient phase-current samples cannot change the calculation.
Both
supported Siemens map generations accept this unambiguous representation.
Measured voltage, power factor and actual power remain useful monitoring data,
but they cannot alter a target or trigger a write.

At an installation limit of `16 A`, the displayed nominal ranges are:

| Reported charger type | Target range | Approximate hardware step |
| --- | ---: | ---: |
| One phase | `1.4..3.7 kW` | `0.23 kW/A` |
| Three phases | `4.1..11.0 kW` | `0.69 kW/A` |

For example, `2.5 kW` on a charger reported as one-phase resolves to `11 A`,
nominally about `2.53 kW`. It is below the physical three-phase minimum of
approximately `4.14 kW` at `6 A`. A one-phase vehicle on a charger reported as
three-phase does not widen this range. This software cannot switch the charger
between one and three phases; register `1642` is read-only on current firmware.

Changing the power target while the charger is paused only updates the resume
target. A target write while the current-limit state is unknown is rejected.
The explicit switch can still send a pause or resume command. If the effective
phase count changed and the stored target is outside the new range, resume is
rejected until a valid target is selected.

## Upgrade and staged verification

Install V26.09.08, restart Home Assistant completely and initially leave all
VersiCharge write entities disabled. Confirm stable monitoring first. Then
enable only **Charging enabled** and **Charging power target**, test one manual
pause/resume and one setpoint on a non-critical charging session, and only then
enable the PV automation. Do not invoke charging commands more often than every
five seconds; a slower interval such as 15 seconds is recommended.

The kW target keeps the existing power-entity unique ID, but its native unit
changes from `W` to `kW`. Existing automations must therefore send values such
as `2.5`, not `2500`. The retired direct-current entity may remain in the Home
Assistant entity registry as unavailable and can be removed manually after its
use in automations has been ruled out.
