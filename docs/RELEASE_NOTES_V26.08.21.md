# V26.08.21: Initial HACS release

First public release candidate of the Siemens SENTRON custom integration for
Home Assistant.

## What's changed

### Added

- Powercenter 1000, 1100 and 2000 root-device support.
- Automatic discovery of supported Powercenter child devices on Modbus unit
  IDs 1–24.
- Standalone PAC2200 support with current, voltage, power, energy, frequency,
  power-factor and diagnostic entities.
- Supported child-device profiles for SENTRON circuit protection, switching,
  monitoring and digital I/O families listed in the README.
- English and German UI translations, stable English entity IDs and a linked
  Home Assistant device hierarchy.
- Sensors, diagnostics and guarded control/configuration entities according to
  each detected profile.
- HACS, Hassfest, repository-contract and Home Assistant runtime-import checks.

### Safety and reliability

- Modbus operations are serialized and write requests are never automatically
  replayed.
- Write-capable entities are disabled by default.
- The potentially irreversible ECPD permanent-disconnect command is disabled by
  default and explicitly labelled.
- A write succeeds only after a positive protocol acknowledgement or verified
  readback where applicable.

## Compatibility

- Home Assistant `2026.8.0` or newer.
- Validated CI target: Home Assistant `2026.8.3`, Python `3.14.2` and
  `pymodbus 3.13.1`.
- Local Modbus TCP connection, normally port `502`.

The presence of a software profile does not mean that every hardware and
firmware combination has been physically validated. Review the README, known
limitations and safety notice before enabling controls.

## Installation

Add `https://github.com/powerassistant/ha-siemens-sentron` to HACS as a custom
**Integration**, select release `V26.08.21`, download it and restart Home
Assistant. Then add **Siemens SENTRON** under **Settings → Devices & services**.

Do not upload a separate integration ZIP as a GitHub Release asset. HACS uses
the automatically generated source archive of this full GitHub Release.

## Upgrade note

Existing entity IDs, including user-customized IDs, are not renamed
automatically. Freshly created entities use config-entry- and device-scoped
English IDs. The diagnostic Modbus address entity is named `unit_id`.

## Important safety note

Write commands can operate physical electrical equipment. The integration is
not a protective device, safety function or substitute for qualified
commissioning. Use only on a trusted local network and validate all commands on
an isolated installation.

The project is MIT-licensed and provided AS IS. See `DISCLAIMER.md`; mandatory
law remains unaffected.
