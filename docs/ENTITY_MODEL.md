# Entity model

## Naming

- Translation keys remain technical, stable and language-independent.
- Entity IDs use canonical English snake case.
- Most SENTRON meter display names start with the measurement family to keep related entities adjacent; VersiCharge uses charger-oriented names such as **Charging power** and **Total charged energy**.
- A collective or aggregate value has no phase suffix.
- Multi-phase values add `L1`, `L2`, `L3` or `N` only when the phase is part of the data point.

Examples:

| Data point | English display name | Canonical object ID |
| --- | --- | --- |
| Aggregate active power | Power Active | `power_active` |
| Phase L1 active power | Power Active L1 | `power_active_l1` |
| Aggregate import energy | Energy Active Import | `energy_active_import` |
| Average phase-neutral voltage | Voltage L-N | `voltage_l_n` |
| Modbus device address | Modbus unit ID | `unit_id` |

## Home Assistant placement

| Home Assistant section | Content |
| --- | --- |
| Device info | Manufacturer, model, firmware, hierarchy and configuration URL |
| Controls | Operational switching and test controls |
| Sensors | Measurements, operating states and protection alarms |
| Configuration | Writable thresholds, selectors, unlocks and other parameters |
| Diagnostics | Firmware, variant, unit ID, connectivity, signal strength and cooldowns |

Unsupported capabilities do not create entities. A supported data point with an invalid current value remains present with an unknown state. Communication failure makes the affected entity unavailable.

## Device hierarchy

Each Powercenter-connected device is represented as its own Home Assistant
device and linked to its Powercenter with `via_device_id`. PAC2200 and
VersiCharge are standalone root devices and never receive Powercenter child
profiles.

## VersiCharge root entities

VersiCharge entities belong directly to one standalone root device at the
detected Modbus unit ID. The supported entity set is created from the documented
map. A missing individual register normally produces an `unknown` state; a
failed coordinator update, or a control whose required register is missing,
produces `unavailable`. Explicitly documented derived values are identified
below.

### Energy and live power

| Value | HA metadata | Default | Purpose |
| --- | --- | --- | --- |
| Total charged energy | `energy`, `kWh`, `total_increasing` | Enabled | Native Home Assistant Energy Dashboard consumption source |
| Charging power | `power`, `W`, `measurement` | Enabled | Derived sum of valid native phase powers for live displays and control feedback |
| Active power L1/L2/L3 | `power`, `W`, `measurement` | Disabled | Optional native phase diagnostics |
| Charger-reported total active power | `power`, `W`, `measurement`, diagnostic | Disabled | Raw aggregate register for comparing charger firmware behavior |
| Power Apparent L1/L2/L3/Total | `apparent_power`, `VA`, `measurement` | Disabled | Optional electrical detail |
| Power Reactive L1/L2/L3/Total | `reactive_power`, `var`, `measurement` | Disabled | Optional electrical detail |

The published aggregate active power is intentionally derived from the sum of
valid phase values; the charger-reported aggregate remains available as a
disabled diagnostic. The cumulative energy sensor suppresses isolated
lower/zero readings and seeds its guard from the Home Assistant restored state
after an entry reload before publishing to long-term statistics.

### Charging state and electrical measurements

| Family | Values | Default |
| --- | --- | --- |
| State | EVSE state, OCPP state, error, charging-current limit, phase mode | Enabled |
| Binary state | Vehicle connected (`versicharge_vehicle_connected`), charging (`versicharge_charging`), problem (`versicharge_problem`) | Enabled |
| Current | L1, L2, L3 and charger phase sum | Enabled |
| Voltage L-N | L1-N, L2-N and L3-N | Enabled |
| Voltage L-L | L1-L2, L2-L3 and L3-L1 | Disabled |
| Power factor | L1, L2, L3 and average | Disabled |
| Temperature | On-board A/B and off-board/cable A/B | Disabled diagnostic |
| Derived limits | Minimum and maximum charging power | Minimum enabled; maximum disabled |

The minimum and maximum charging-power sensors are derived estimates for the
reported charger phase type and live voltage/power-factor values. The editable
`kW` target instead uses stable nominal-230-V bounds for that charger phase type,
so its Home Assistant input range does not move on every telemetry poll. Both
reflect the charger’s `6 A` minimum through its installation-current maximum
(falling back to rated current and then `16 A`).

### Identification and diagnostics

VersiCharge diagnostics include the installation and rated current, production
date, platform and outlet type, commissioning connectivity, meter type, A8 and
M0 firmware, Modbus application version, firmware variant/release date,
selected register-map profile and Modbus unit ID. Less frequently needed items
are disabled by default to keep the device page focused.

Config-entry diagnostics redact host, serial number and internal identifiers.
They are intended for fault reports and do not add writable shortcuts.

### Disabled-by-default controls

| Entity key | Native action | Range / behavior |
| --- | --- | --- |
| `versicharge_charging_enabled` | Register `1633` | Off writes `0 A`; on resumes the valid in-memory target |
| `versicharge_charging_power` | Deterministic conversion to register `1633` | `0.1 kW` UI step within stable phase-specific bounds; nominal `230 V` conversion rounded half-up to a whole ampere |
| `versicharge_fallback_current` | Register `1660` | `0 A` or `6 A` to installation maximum |
| `versicharge_fallback_time` | Register `1661` | `0 s` or `60–600 s` |

All four entities are disabled in the Home Assistant entity registry until the
user deliberately enables them. Changing the power target while charging is
paused updates only the remembered resume target; enabling charging converts
and applies that target. A target change is rejected while the current-limit
state is unknown.

Each physical command is attempted once and requires a positive Modbus
acknowledgement. There is no command retry, two-second sleep or immediate
readback. The later normal read-only poll independently reports register
`1633`. A running command rejects a concurrent call immediately. Physical
power-target writes and resume starts have a five-second start-to-start limit;
pause and fallback may bypass that interval but not the fail-fast guard.
Local-only target changes use a separate limiter and therefore do not delay an
immediate resume. All VersiCharge commands have a twelve-second hard deadline.

The target is retained only while the config entry stays loaded. Following a
Home Assistant restart or entry reload, an active whole-ampere current limit is
adopted as a nominal `kW` target; a paused charger receives the phase-specific
minimum as its resume target after a valid poll. A missing limit read does not
hide the controls, but it prevents a changed target from being committed.

Register `1633` is written only with whole amperes. The power entity accepts a
`0.1 kW` UI step and presents the requested target as stable configuration
state. This input granularity does not create fractional-ampere hardware
resolution: the approximate physical step is `0.23 kW/A` for one phase and
`0.69 kW/A` for three phases at nominal voltage. Measured voltage, power factor
and actual power remain read-only monitoring data and never recalculate or
rewrite the target. The measured **Charging power** sensor remains the actual
result.

Fallback current and time are written together once, require a positive
acknowledgement and are not persistent across a charger power cycle or soft
reset. `0 A` and `60 s` are the recommended initial values for PV-only
operation, subject to installation-specific validation.

### Phase-mode policy

The command calculation uses only the stable charger type reported by register
`1642`: `0` means one-phase and `1` means three-phase. Phase-current samples are
monitoring data and cannot alter the control phase count; this avoids a
factor-three command change after a transient L2/L3 zero. Consequently, a
one-phase vehicle connected to a three-phase charger does not widen the target
range. Siemens marks register `1642` read-only from firmware `2.135`, and this
release does not write it even for a legacy charger. Automatic 1/3-phase
switching requires separately supported hardware with its own safe switching
and interlock implementation.
