# Changelog

All notable changes to this project are documented here.

## [V26.09.08] - 2026-09-07

### Fixed

- Removed the unbounded VersiCharge service-call backlog: a command already in
  progress now rejects concurrent calls immediately instead of adding another
  waiter to the coordinator write lock.
- Removed the delayed two-second command readback that kept the write lock busy
  and amplified Modbus timeouts. A command is written once, requires a positive
  FC06 acknowledgement and is observed passively by the next normal poll.
- Decoupled VersiCharge polling from all command locks. Slow or failed read
  cycles can no longer hold queued charging-power service calls.

### Changed

- Replaced the dual current/power target model with one charging-power target
  in `kW`, using a `0.1 kW` Home Assistant step.
- Convert the requested target exactly once using nominal `230 V` and the
  stable charger phase type reported by register `1642`, round half-up to a
  whole ampere and write that unambiguous whole-A value to register `1633`.
- Live voltage and power-factor measurements remain available for monitoring
  but no longer influence commands or cause the same power target to resolve to
  a different current on later calls.
- Removed phase-current inference from the command calculation, so a transient
  zero reading on L2/L3 cannot change the requested current by a factor of three.
- Removed the writable direct-current target. The read-only current-limit
  sensor remains available for diagnostics and automations.
- Reduced normal VersiCharge traffic to a read-only `10 s` poll with a `5 s`
  request timeout; static identity is no longer reread every five minutes.
- Active power-target and resume writes now have a five-second start-to-start
  limit. Pause and fallback may bypass that interval but still fail fast while
  another command is active. Every write has a twelve-second outer deadline,
  with no retry or automatic corrective write.

## [V26.09.07] - 2026-09-06

### Fixed

- Accept the VersiCharge firmware's whole-ampere readback after fractional
  current commands. For example, the observed `14.49 A` command followed by a
  `15 A` readback is now treated as successfully applied instead of raising a
  false service error.
- Keep charging-current and charging-power targets available when the isolated
  register `1633` read is temporarily missing or unavailable.
- Initialize a paused charger with a safe `6 A` resume target and its derived
  Watt value so the target fields are not blank after a restart.

### Changed

- Normalize both the documented whole-ampere readback and a defensive modern
  centiampere echo while retaining the raw register value for diagnostics.
- Suppress telemetry-only redraws for both current and power target controls;
  write acknowledgement and bounded readback verification remain required.
- Use stable nominal-230-V input bounds while retaining live voltage and power
  factor for conversion, so frontend limits no longer drift between polls.
- Recalculate Watt-based resume current for the currently detected phase mode
  and reject a stale target that is outside the new phase-specific range.

## [V26.09.06] - 2026-09-06

### Fixed

- Prevented the five-second VersiCharge telemetry refresh from redrawing the
  editable charging-power box and overwriting a value while it is being typed.
- Removed volatile measured power from the Number entity; actual charging power
  remains available through its dedicated Sensor entity.

### Changed

- Charging-power input now accepts every whole-Watt value between its dynamic
  minimum and maximum instead of using `50 W` UI steps.
- Confirmed modern firmware converts Watt targets with the supported `0.01 A`
  command resolution. The exact requested Watt target remains visible in Home
  Assistant while physical power remains measurement-dependent.

## [V26.09.05] - 2026-09-05

### Added

- Standalone VersiCharge AC Gen3 root-device detection, using configured unit
  ID `2` by default and automatic fallback to unit ID `1`.
- VersiCharge charging energy and active-power entities for the Home Assistant
  Energy Dashboard, plus phase electrical measurements, state, fault,
  temperature, firmware and installation diagnostics.
- Disabled-by-default VersiCharge charging-current, virtual active-power,
  pause/resume and native fallback controls with acknowledgement and readback.
- A watt-to-ampere conversion based on the charger’s measured phase-to-neutral
  voltages, per-phase power factors and observed one- or three-phase mode.
- Firmware-aware handling for the legacy 2023 and current 2025 Modbus maps,
  including energy, power-factor, status and current-command differences.
- A dedicated VersiCharge guide with an example PV-surplus automation and
  fail-safe configuration notes.

### Changed

- VersiCharge live values use a 5-second coordinator interval and the Modbus
  client retains a 15-second timeout, satisfying the current map’s minimum
  timing requirements.
- Isolated VersiCharge cumulative-energy drops are filtered before they can
  distort Home Assistant long-term statistics; the filter is seeded from the
  restored entity state after an integration reload.
- VersiCharge writes wait the documented two-second poll interval before one
  readback and deduplicate unchanged current targets without replaying writes.

### Safety and compatibility notes

- Every new write-capable entity remains disabled by default.
- The phase-mode register is observation-only in this release. Siemens marks
  it read-only on firmware `2.135` and newer, so automatic 1/3-phase switching
  is not performed.
- OCPP or cloud-side limits can take precedence over Modbus commands. Actual
  charging power must be used as control feedback.
- Software tests do not constitute hardware validation. Real-device testing
  across the supported firmware and electrical configurations remains required.

## [V26.08.21] - 2026-08-21

### Added

- Standalone SENTRON PAC2200 root-device support.
- Powercenter 1000, 1100 and 2000 root-device classification.
- Unified Powercenter device profiles with separate Home Assistant devices and current `via_device_id` parent relationships.
- English and German translations, entity icons and collision-free English default entity IDs.
- Protected ECPD configuration, RCM thresholds, test commands and command cooldown handling.
- GitHub/HACS repository structure, validation workflows and release documentation.

### Changed

- Generalized onboarding text for both Powercenter and PAC2200.
- Renamed the diagnostic Modbus address entity to `unit_id`.
- Moved identification and connection information into diagnostics and writable parameters into configuration where appropriate.
- Updated device-card links to global Siemens SENTRON product pages.
- Marked the ECPD permanent-disconnect action explicitly and disabled it by default.
- Added the MIT License plus explicit safety, warranty, liability and trademark notices.
- Serialized Modbus I/O, removed command replay and require a positive ACK or verified readback for writes.
- Reduced polling and topology-discovery load and retained a stable detected root-device type.
- Aligned the CI runtime with Home Assistant 2026.8.3 on Python 3.14.2 and its
  `pymodbus 3.13.1` constraint.
- Reworked the README into an end-user release guide with compatibility,
  preparation, HACS, Energy Dashboard and screenshot sections.

### Upgrade note

Existing entity IDs are preserved, including user-customized IDs. New entities receive collision-free English defaults scoped to their config entry and device.
