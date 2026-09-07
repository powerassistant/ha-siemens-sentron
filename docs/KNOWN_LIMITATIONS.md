# Known limitations

These limits apply to release `V26.09.08`.

- This is a custom community integration, not a Home Assistant Core
  integration and not a certified safety or billing component.
- Home Assistant `2026.8.0` or newer is required. The tested CI target is Home
  Assistant `2026.8.3` on Python `3.14.2` with `pymodbus 3.13.1`.
- A Powercenter scan covers Modbus unit IDs 1–24. Devices outside that range are
  not discovered by this release.
- PAC2200 is handled as a standalone root device on its defined Modbus unit; it
  does not trigger Powercenter child discovery.
- VersiCharge AC Gen3 is also a standalone root device and does not trigger
  Powercenter child discovery. Detection defaults to unit ID `2`, retries `1`,
  and permits a different configured address.
- Only one Home Assistant config entry may use the same host and TCP port.
- Modbus TCP does not provide encryption or authentication. The device network
  must be isolated and access-controlled.
- Available entities depend on the detected device profile and firmware.
  Presence of a software profile does not establish that every firmware and
  hardware combination has been physically validated.
- Write-capable entities are disabled by default. They must be individually
  enabled and tested on a non-critical installation before operational use.
- The ECPD permanent-disconnect command can be irreversible and remains
  disabled by default.
- Existing entity IDs are preserved during upgrades. Fresh entities use the
  current collision-free naming scheme, so a clean installation can have IDs
  that differ from an older installation.
- Product-state diagrams and source manuals are intentionally not bundled.
  README screenshot graphics are clearly labelled placeholders until sanitized
  Home Assistant captures with confirmed publication rights are provided.

## VersiCharge-specific limits

- Modbus is disabled by default on current VersiCharge firmware. The charger
  must be commissioned and its Modbus application enabled through Sifinity Go
  or Siemens Support; this integration cannot enable it remotely.
- Current firmware requires at least a five-second client timeout and at least
  two seconds between polls. This integration uses a five-second VersiCharge
  request timeout and a ten-second coordinator interval, but other Modbus
  clients can still exhaust charger resources or disturb timing.
- Firmware below `2.135` and firmware `2.135` or newer use different total-
  energy and power-factor scaling. Unknown firmware is interpreted with current
  map semantics. Confirm the displayed firmware profile and compare readings
  with a known reference before using statistics or load control.
- The current 2025 map changes EVSE and fault semantics around firmware `2.136`.
  An unlisted future code is exposed as unknown rather than guessed.
- Release V26.09.08 deliberately uses only whole-ampere commands for register
  `1633` on every supported register-map generation. The former direct-current
  target and fractional-ampere write path are no longer exposed.
- A missing read of register `1633` makes the limit feedback unknown but no
  longer hides the separate target controls. A changed power target is rejected
  until the state is known. Every physical command still requires a positive
  acknowledgement; its independent result is observed by a later read-only
  poll rather than an immediate readback.
- The controllable floor is `6 A`. At nominal `230 V` and power factor 1 this is
  about `1.38 kW` single-phase or `4.14 kW` three-phase. Surplus below that
  floor must pause charging; it cannot be represented as a lower continuous
  setpoint.
- The `0.1 kW` power target is not a native charger register. It converts once
  with nominal `230 V` and the stable charger phase type reported by register
  `1642`, then rounds half-up to a whole ampere. Measured phase currents,
  voltage and power factor do not refine or feed back into the target. Vehicle
  behavior, voltage changes and whole-ampere rounding can therefore make actual
  power differ from the request.
- A one-phase vehicle on a charger reported as three-phase does not change the
  control phase count or expose the one-phase target range. This conservative
  rule avoids a factor-three command error from transient current readings.
- The `0.1 kW` UI step is finer than the charger’s effective power resolution:
  one ampere represents approximately `0.23 kW` single-phase or `0.69 kW`
  three-phase at nominal voltage. Multiple adjacent `kW` inputs can resolve to
  the same current command.
- VersiCharge commands are not queued or retried. A concurrent command is
  rejected immediately; physical power-target writes and resume starts have a
  five-second start-to-start limit, while local-only target changes are
  throttled separately. Pause and fallback may bypass the interval but never
  the active-command guard. Each write has a twelve-second hard deadline. An
  automation must handle rejection and should normally update no faster than
  every 15 seconds.
- Phase mode is read-only on firmware `2.135` and newer. This integration does
  not perform automatic 1/3-phase switching on any firmware. External phase-
  switching hardware needs independent electrical interlocking, vehicle-safe
  sequencing and explicit integration support.
- Fallback current and fallback time are not persistent after a charger power
  cycle or soft reset. `0 A`/`60 s` is a conservative PV-only recommendation,
  not a value the integration silently forces. Automations should verify it
  after every charger restart.
- OCPP or cloud-side charging policies can override, clamp or race a Modbus
  command. Requested current/power is therefore not authoritative; always use
  actual active power and state as feedback.
- The charger can temporarily return zero or stale register data while internal
  messages are missing. The integration filters isolated cumulative-energy
  drops, but instantaneous sensors can still lag by multiple update cycles.
- Session-energy-target, delay, reset, factory-reset and RFID-list writes are
  not exposed. Current vendor maps either make them read-only, describe their
  units ambiguously, or give them destructive/security-sensitive effects.
- Software decoding, conversion and integration tests do not establish
  physical compatibility. VersiCharge hardware validation across firmware,
  one-/three-phase wiring, current ratings, communication loss and OCPP
  combinations remains outstanding for this release.

For reproducible integration defects, use the repository bug-report form. For
a new device or firmware variant, use the device-support form and provide only
information that may legally be published.
