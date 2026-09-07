# VersiCharge monitoring and PV-surplus control

Release `V26.09.08` supports Siemens VersiCharge AC Gen3 as a standalone
Modbus TCP root device. It provides Energy Dashboard measurements and one
guarded `0.1 kW` charging target without pretending that the charger has a
native power register.

## Commissioning and setup

1. Commission the charger according to Siemens documentation.
2. Enable Modbus through Sifinity Go or Siemens Support. Current firmware ships
   with Modbus disabled, and Home Assistant cannot enable it remotely.
3. Give the charger a stable local IP address and keep TCP port `502` on an
   isolated, trusted network.
4. Add **Siemens SENTRON** from **Settings → Devices & services**.
5. Leave the Modbus unit ID at `2` unless the installation uses another value.
   With the default, the integration automatically tries unit `1` if unit `2`
   does not identify a VersiCharge.

VersiCharge uses a `10 s` live polling interval and a `5 s` Modbus request
timeout. The current Siemens map requires a timeout of at least five seconds
and a polling interval of at least two seconds. Identification, firmware and
other immutable configuration values are read during discovery and are not
refetched periodically. Avoid a second client polling the same charger
aggressively.

## Monitoring

The default device page includes:

- cumulative charging energy in `kWh`;
- actual aggregate active power in `W`;
- EVSE and OCPP state, error and derived problem signals;
- vehicle-connected and charging binary sensors;
- phase mode and charging-current limit;
- current L1/L2/L3 and phase sum;
- voltage L1-N/L2-N/L3-N;
- minimum charging-power estimate;
- installation current, A8 firmware, register profile and Modbus unit ID.

Additional phase power, line-to-line voltage, apparent/reactive power, power
factor, temperature, fallback and identity diagnostics are available but some
are disabled by default.

### Home Assistant Energy Dashboard

Under **Settings → Dashboards → Energy**, add the VersiCharge **Total charged
energy** sensor as an individual-device or consumption energy source. It has
unit `kWh`, device class `energy` and state class `total_increasing`.

Use **Charging power** for the live device card and PV automation feedback. It
is a `W` measurement, not a replacement for the cumulative energy entity. The
integration filters isolated lower/zero energy-counter samples and seeds that
guard from Home Assistant's restored entity state after an integration reload,
protecting long-term statistics from a false reset spike.

## Firmware-dependent decoding

The attached `09/2023` map and the current Siemens `02/2025` map use the same
core measurements but not the same scaling and command semantics.

| Behavior | Firmware below 2.135 | Firmware 2.135 and newer |
| --- | --- | --- |
| Total energy | raw × `0.0001 kWh` | raw × `0.001 kWh` |
| Power factor | raw × `0.01` | raw × `0.001` |
| Register 1633 input | Whole amperes | Whole amperes or encoded hundredths of an ampere |
| V26.09.08 write policy | Whole amperes only | Whole amperes only |
| Current-register decoding | Whole amperes | Whole amperes; defensive centiampere decoding |
| Phase register | Legacy map describes RW | Read-only |

Firmware `2.136` also changes EVSE states and the error-code table. The
integration selects separate scaling and state profiles from the A8 firmware.
If the string is missing or unparseable, a successfully read extension block
that exists only on modern firmware confirms the modern profile. Without that
evidence, current-map scaling is assumed. Charging commands always use the
cross-firmware whole-ampere form. No phase write is enabled in either case.
The specifically reported firmware `2.500.34+25-32` is recognized as newer than
`2.135` and therefore selects the modern profile; this example does not change
the general profile thresholds above.

## Controlling kW through an ampere register

The charger accepts a current limit at Modbus offset `1633`. The integration
adds one virtual **Charging power target** number entity so a Home Assistant
automation can work in `kW`. Its input step is `0.1 kW`. Each accepted value is
rounded half-up to one decimal place and converted exactly once:

\[
I_{target} = \operatorname{round\_half\_up}
\left(\frac{P_{target,kW}\times1000}{230\times n_{phases}}\right)
\]

The resulting whole ampere is written directly. Measured voltage, power factor
and actual power remain monitoring values only: they do not participate in the
target calculation, cannot change the remembered target and cannot trigger a
write. This deliberately prevents a measurement/write feedback path.

The stable input range uses nominal `230 V`, the charger phase type reported by
register `1642` and the
physical `6 A` through installation-current limits. The maximum installation
current falls back to rated current and then `16 A` if it cannot be read. At a
`16 A` installation limit:

| Mode | Input range | Approximate physical step |
| --- | ---: | ---: |
| One phase | `1.4..3.7 kW` | `0.23 kW/A` |
| Three phases | `4.1..11.0 kW` | `0.69 kW/A` |

Several adjacent `0.1 kW` inputs can therefore resolve to the same whole-ampere
command. For example, `2.5 kW` on a charger reported as one-phase resolves to
`11 A`, nominally about `2.53 kW`. A value below `4.1 kW` is outside the
displayed range of a charger reported as three-phase. If the charger phase type
is unknown, the target entity is unavailable
instead of risking a threefold error. Use the measured **Charging power** sensor
to observe the real result.

The requested kW value is user-owned state. It is initialized once from a valid
active current limit, or otherwise from the minimum nominal target. Later
telemetry and register reads never convert amperes back into the input value.
Volatile measurement refreshes therefore do not redraw the editable number box.

## 1/3-phase switching

The command calculation uses only the stable charger type reported by register
`1642`. Live phase-current samples remain monitoring data and cannot change a
target calculation. This avoids a factor-three current error if L2/L3 are
temporarily read as zero. It also means that a one-phase vehicle connected to a
charger reported as three-phase does not unlock the one-phase target range.

Siemens marks the phase register read-only on firmware `2.135` and newer. Even
though the older map describes a writable value, this release keeps it
observation-only on all firmware rather than exposing a control that may be
ignored or unsafe. Automatic 1/3-phase switching would require separately
supported switching hardware, safe contactor sequencing, vehicle-state checks
and electrical interlocking.

## Safe control setup

All VersiCharge controls are disabled by default. Enable only the entities you
intend to test:

1. Open **Settings → Devices & services**, select **Siemens SENTRON**, then
   open the VersiCharge device.
2. Expand the section containing entities that are not shown, select one
   control, open its cogwheel and turn on **Enable**. Select **Update** and wait
   for Home Assistant to activate it.
3. Start with **Charging enabled** and **Charging power target** only. Enable
   fallback controls separately when you are ready to test connection loss.

- **Charging enabled** (`versicharge_charging_enabled`): pause (`0 A`) and
  resume the valid target remembered for the current loaded config entry;
- **Charging power target** (`versicharge_charging_power`): the only charge
  target, entered in `0.1 kW` steps and converted to a whole-ampere command;
- **Fallback current** (`versicharge_fallback_current`) and **Fallback time**
  (`versicharge_fallback_time`): native communication-loss policy.

The three derived binary-sensor keys are `versicharge_vehicle_connected`,
`versicharge_charging` and `versicharge_problem`. Home Assistant entity IDs are
scoped to the config entry, so copy the exact IDs from your own entity registry.

The former direct **Charging current target** writer is no longer created. An
old entity-registry entry can remain unavailable after the upgrade and may be
removed once no automation references it.

For PV-only operation, start with fallback current `0 A` and fallback time
`60 s`. The pair is written atomically with one FC16 request. A positive
acknowledgement is required, but there is no immediate readback; the next normal
read-only poll reports the independent charger values. The setting is not
persistent in the charger, so verify or reapply it after every charger power
cycle or soft reset. The integration does not silently force that policy
because a different fallback may be required for the installation.

Each current-limit command consists of exactly one FC06 write with a positive
acknowledgement. There is no retry, sleep or immediate readback. A command has a
`12 s` hard deadline, while the Modbus request timeout is `5 s`; the subsequent
normal poll performs independent observation. Concurrent VersiCharge commands
are rejected immediately instead of queued. Physical power-target writes and
resume starts are limited to one per `5 s`; pause and fallback may bypass that
interval but never the active-command guard. Local-only target changes use a
separate limiter and therefore do not delay an immediate resume. Repeated
unchanged targets that already match the observed whole-ampere limit are
complete no-ops. These guards prevent command backlog; they do not resolve
competing controllers. If OCPP or a cloud policy is active, it can clamp,
override or race local Modbus commands.

A changed kW target while charging requires a fresh value from register `1633`;
otherwise the request is rejected without changing the remembered target. An
explicit pause is not held behind the normal rate-limit interval, but it is
still rejected immediately if another VersiCharge command is already active.

The resume target is deliberately not persisted: after a Home Assistant restart
or config-entry reload, a paused charger starts with the minimum nominal kW
target unless an automation sets another target first. Before resuming, the
stored kW value is checked against the currently reported charger type. If that
type is unavailable or the target lies outside its range, resume is rejected
until a valid target is selected. Changing the power target while paused only
updates this resume value and performs no Modbus write.

The fallback registers have discontinuous native ranges: current accepts `0`
or `6` through the installation limit, and time accepts `0` or `60` through
`600 s`. Home Assistant number boxes cannot hide the gaps, so values `1..5 A`
or `1..59 s` are rejected with a service error.

## Example PV-surplus automation

Replace the example entity IDs with the IDs from your Home Assistant instance.
The grid-export sensor in this example must be positive while exporting. Enable
the VersiCharge maximum-power sensor or replace it with a fixed site limit.

Create the reserve used below under **Settings → Devices & services → Helpers →
Create helper → Number**. Name it **PV export reserve**, use a range such as
`0` to `3000`, step `50`, unit `W`, and numeric-input mode. Confirm that its
entity ID is `input_number.pv_export_reserve` or replace that ID in the example.

The essential calculation is:

\[
P_{available} = \max(0,
P_{charger\ measured} + P_{grid\ export} - P_{reserve})
\]

Adding the charger’s current measured power is important. If the car already
charges at `2 kW` while another `2 kW` is exported, the new target is roughly
`4 kW` minus the reserve—not merely the remaining `2 kW` export.

```yaml
alias: VersiCharge PV surplus
mode: single

trigger:
  - platform: time_pattern
    seconds: "/15"

condition:
  - condition: template
    value_template: >-
      {{ states('sensor.grid_export_power') not in ['unknown', 'unavailable']
         and states('sensor.versicharge_active_power_total')
             not in ['unknown', 'unavailable'] }}

action:
  - variables:
      charger_w: >-
        {{ states('sensor.versicharge_active_power_total') | float(0) }}
      export_w: >-
        {{ states('sensor.grid_export_power') | float(0) }}
      reserve_w: >-
        {{ states('input_number.pv_export_reserve') | float(0) }}
      available_kw: >-
        {{ [((charger_w + export_w - reserve_w) / 1000), 0] | max }}
      minimum_kw: >-
        {{ state_attr('number.versicharge_charging_power', 'min') | float(4.1) }}
      maximum_kw: >-
        {{ state_attr('number.versicharge_charging_power', 'max') | float(11.0) }}

  - choose:
      - conditions: "{{ available_kw < minimum_kw }}"
        sequence:
          - service: switch.turn_off
            target:
              entity_id: switch.versicharge_charging_enabled
    default:
      - service: number.set_value
        target:
          entity_id: number.versicharge_charging_power
        data:
          value: >-
            {{ [available_kw, maximum_kw] | min | round(1) }}
      - service: switch.turn_on
        target:
          entity_id: switch.versicharge_charging_enabled
```

For production use, add start/stop hysteresis, minimum on/off times and any
house-battery policy required by the site. A signed grid-power sensor must first
be normalized to a positive-export value. Do not run the example faster than
the measurement path can update; `15 s` is intentionally slower than the
integration’s `10 s` polling and the command rate limit.

## Verification checklist

Before enabling an automation on a production installation:

1. Confirm model, A8 firmware, register profile and unit ID diagnostics.
2. Compare voltage, current, power factor, active power and cumulative energy
   with the charger UI or a trusted meter.
3. Verify the displayed phase mode; a power command is unavailable if phase
   mode cannot be established safely.
4. Test one pause/resume and one kW target on a non-critical session.
5. Confirm measured active power follows the command within expected charger
   and vehicle tolerance.
6. Disconnect Modbus and verify the chosen fallback behavior, then repeat after
   a charger power cycle.
7. If OCPP is configured, test its priority and conflict behavior explicitly.

For troubleshooting, optionally enable the disabled **Effective phase count**
diagnostic; it mirrors the stable charger type used by the calculation. To
collect a report, open **Settings → Devices & services → Siemens
SENTRON**, use the three-dot menu and select **Download diagnostics**. Review
the JSON before sharing it even though host, serial number and internal IDs are
redacted by the integration.

This release includes software-level decoding and conversion checks. It does
not claim completed physical-device validation across the firmware, phase and
OCPP combinations above.

## Register-map reference

Use the current
[Siemens VersiCharge AC Series Modbus map](https://support.industry.siemens.com/cs/document/109814359/versicharge-ac-series-modbus-map?dti=0&lc=en-WW)
for commissioning and firmware-specific limits. The integration does not bundle
the source manual.
