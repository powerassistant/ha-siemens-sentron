# Release status: V26.09.08

This tree is a GitHub/HACS release candidate, not an authorization to publish.

## Completed locally

- Standard HACS integration layout under `custom_components/siemens_sentron`.
- Manifest, HACS metadata, GitHub owner URLs and version synchronized to
  `powerassistant/ha-siemens-sentron` and `V26.09.08`.
- MIT License, safety disclaimer, contribution rights policy and security policy.
- Maintainer-confirmed Siemens brand-asset authorization recorded in
  `NOTICE.md`, `DISCLAIMER.md` and `PUBLICATION_CHECKLIST.md`.
- No bundled PDF, spreadsheet, manual, register-map source file or product-state
  screenshot.
- Python compilation, dependency-free contract tests and the repository
  validator pass locally.
- GitHub Actions are configured for repository checks, HACS Action, Hassfest and
  runtime imports against Home Assistant 2026.8.3 on Python 3.14.2 with
  pymodbus 3.13.1.
- The public README follows an end-user-oriented release layout with HACS,
  compatibility, setup, Energy Dashboard and screenshot sections.
- Standalone VersiCharge AC Gen3 root-device support is integrated without
  mixing its register model with PAC2200 or Powercenter datasets.
- VersiCharge discovery uses configured unit ID `2` by default and retries unit
  ID `1`; a different address can be supplied during onboarding.
- The implementation has firmware-aware decoding for the legacy `09/2023` and
  current `02/2025` register maps, including energy and power-factor scaling,
  status/error semantics and the whole-ampere current command.
- Energy Dashboard entities, live electrical measurements, state/fault and
  device diagnostics are defined for VersiCharge.
- The single VersiCharge power target, charging switch and fallback controls
  are disabled by default. Physical commands require a positive Modbus
  acknowledgement; independent state is observed by the later read-only poll.
- The power input uses `kW` with a stable `0.1 kW` step. It converts once with
  nominal `230 V` and the stable charger phase type from register `1642`,
  rounds half-up to a whole
  ampere and writes that unambiguous value to register `1633`.
- Measured voltage, power factor and actual power remain monitoring data; they
  neither recalculate the remembered target nor trigger a write.
- Phase-current samples cannot switch the command calculation between one and
  three phases.
- The former direct current target, fractional-ampere commands, delayed
  readback verification and automatic command retries have been removed.
- A command already in progress rejects concurrent calls immediately instead
  of queueing waiters. Power-target writes and resume starts have a five-second
  start-to-start limit; pause and fallback may bypass that interval but not the
  shared fail-fast guard. Local-only target changes have a separate limiter, so
  they cannot create listener floods or delay an immediate resume. Every write
  has one attempt and a twelve-second hard deadline.
- VersiCharge polling is read-only, runs every ten seconds with a five-second
  request timeout and does not take the command guard.

## Software validation scope

- Pure decoding and conversion tests cover address blocks, signed/unsigned
  values, firmware-dependent scaling, deterministic kW-to-whole-ampere
  conversion and cumulative energy filtering.
- Integration contract tests cover the platform/configuration surface and
  repository metadata.
- Python compilation, dependency-free contract tests and the repository
  validator are release gates. Passing them establishes software consistency,
  not electrical behavior on a physical charger.

## Hardware validation still required

- The load-safety redesign addresses an unbounded command-waiter path found
  during review of V26.09.07. It is a plausible contributor to the reported
  outage, but the available field evidence does not establish it as the sole
  cause.
- Firmware `2.500.34+25-32` supplied the initial field observations; this does
  not replace the full physical hardware matrix below.
- Validate at least one legacy firmware below `2.135` and current firmware
  `2.135`/`2.136+`, both one-phase and three-phase installations where
  applicable.
- Verify pause/resume, `0.1 kW` input, whole-ampere conversion, fallback
  behavior after communication loss and power cycle, positive acknowledgement,
  subsequent poll feedback, OCPP interaction and every supported
  installation-current limit.
- Stress rapid duplicate and conflicting target calls and a non-responsive
  charger; confirm that commands are rejected rather than queued and that
  monitoring and unrelated Home Assistant automations remain responsive.
- Verify that a real device produces stable Energy Dashboard statistics over
  multiple charging sessions and after restarts.

## Blocking before public release

- Confirm in writing that public distribution of the source code and the
  implemented register/behavior knowledge is authorized.
- Complete any applicable employer, Siemens IP, export-control, product-security
  and open-source approval process.
- Clarify whether provider-identification or imprint duties apply to the actual
  German publication/support model and add the required contact information if
  necessary.
- Confirm that the future Git history contains no confidential, sensitivity-
  labelled, customer-specific or third-party source material.
- Complete the hardware matrix in `PUBLICATION_CHECKLIST.md`, especially every
  write command, negative path, acknowledgement, subsequent polling, fallback
  behavior and rate limit. For VersiCharge, include OCPP/cloud interaction and
  one-/three-phase behavior.
- Push to GitHub and require the HACS, Hassfest, runtime-import and repository
  checks to pass before creating the release.

## Legal scope

The MIT License contains broad permission plus an AS-IS warranty and liability
disclaimer. `DISCLAIMER.md` adds project-specific electrical and operational
warnings. Neither document can override mandatory law, so the repository does
not promise an absolute exclusion of liability.
