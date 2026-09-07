# Publication checklist

Do not make the repository public or create a release until every blocking gate is complete.

## Blocking approval gates

- [ ] Confirm that the rights holder authorizes public distribution of the source code, including register addresses and behavior derived from Siemens technical material.
- [ ] Obtain the required Siemens employer, IP, export-control, product-security and open-source approvals.
- [x] Maintainer confirms that the bundled Siemens brand icon/logo is used in agreement with Siemens.
- [x] Scan this release-candidate tree and confirm that it contains no confidential/source PDF, spreadsheet, product-state screenshot or log.
- [ ] Confirm that no confidential, sensitivity-labelled or customer-specific source file, excerpt, screenshot, metadata or log is present in the final Git history.
- [ ] Determine whether provider-identification or imprint duties (for example § 5 DDG in Germany) apply to the actual publication and support model; if they do, add complete legal contact information before publication.
- [x] Apply the MIT License with copyright holder `powerassistant`.
- [x] Set the repository URL to `powerassistant/ha-siemens-sentron`.
- [x] Set the manifest codeowner to `@powerassistant`.

## Hardware release gates

- [ ] Test installation and upgrade on the supported Home Assistant release.
- [ ] Test the config flow with a PAC2200.
- [ ] Test the config flow with VersiCharge unit ID 2 and the unit ID 1 fallback.
- [ ] Verify VersiCharge energy, phase/state decoding and firmware profile on
  firmware `2.500.34+25-32` against a trusted physical reference.
- [ ] Test the single VersiCharge `0.1 kW` target, deterministic nominal-230-V
  conversion to a whole-ampere command, pause/resume, fallback after connection
  loss and fallback reset after a power cycle on a non-critical one- and
  three-phase setup as applicable.
- [ ] Confirm on hardware that one target sends at most one write, requires a
  positive acknowledgement and is reflected by a later normal poll without an
  immediate readback or automatic retry.
- [ ] Stress rapid duplicate and conflicting target calls plus a non-responsive
  charger; confirm immediate rejection rather than waiter growth, the
  five-second write/resume interval, local-only target throttling, the bounded
  timeout and continued Home Assistant responsiveness.
- [ ] Verify OCPP/cloud priority and both reported one-/three-phase charger
  types; confirm that a one-phase vehicle on a three-phase charger does not
  alter the control phase count and that no phase-switch write is issued.
- [ ] Test the config flow and discovery with each supported Powercenter generation that will be claimed publicly.
- [ ] Test representative read entities for every claimed end-device family.
- [ ] Test every enabled write command, its acknowledgement, subsequent poll
  feedback, failure path and rate-limit behavior on an isolated installation.
- [x] Verify statically that the ECPD permanent-disconnect action is disabled by default and clearly labelled.
- [x] Confirm by automated contract test that existing IDs are not renamed; review the new default IDs on a fresh installation.

## Repository setup

- [ ] Create the public GitHub repository `powerassistant/ha-siemens-sentron`.
- [ ] Set the description to: `Home Assistant custom integration for Siemens SENTRON Powercenter, PAC2200 and VersiCharge over Modbus TCP.`
- [ ] Add topics: `home-assistant`, `hacs`, `custom-component`, `siemens`,
  `sentron`, `versicharge`, `ev-charging`, `modbus`, `modbus-tcp`, `powercenter`, `pac2200`,
  `energy-monitoring`, `power-monitoring`.
- [ ] Enable Issues and private vulnerability reporting.
- [ ] Protect the default branch and require the validation workflow.
- [x] Run `python3 scripts/validate_repository.py` and confirm a clean local result.
- [x] Pin the runtime workflow to Python 3.14.2, Home Assistant 2026.8.3 and the
  compatible `pymodbus 3.13.1` dependency.
- [ ] Confirm HACS Action and Hassfest pass without ignored checks.

## Release V26.09.08

- [x] Confirm `manifest.json` contains `"version": "V26.09.08"`.
- [ ] Create the tag `V26.09.08` only after all checks pass.
- [ ] Create a full GitHub Release titled `V26.09.08: VersiCharge load-safety redesign`;
  a tag alone is insufficient for HACS default-catalog submission.
- [ ] Paste `docs/RELEASE_NOTES_V26.09.08.md` into the release notes.
- [ ] If placeholders are replaced, approve each sanitized Home Assistant
  screenshot according to `docs/images/README.md` and add only the approved
  paths to the repository validator.
- [ ] Do not attach a custom integration ZIP: HACS uses `custom_components/siemens_sentron` from the GitHub release source.
- [ ] Test a clean HACS custom-repository installation and an update from the previous integration version.

## Optional HACS default catalog

- [ ] Confirm the repository owner or a major contributor submits the request.
- [ ] Fork `hacs/default`, create a branch from `master`, and add the repository alphabetically to `integration`.
- [ ] Complete the HACS pull-request template truthfully and allow maintainer edits.
