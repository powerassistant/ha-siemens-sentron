<p align="center">
  <img src="https://raw.githubusercontent.com/powerassistant/ha-siemens-sentron/main/custom_components/siemens_sentron/brand/logo.png" alt="Siemens SENTRON" width="120">
</p>

# Siemens SENTRON for Home Assistant

## Turn electrical measurements into a smarter home.

See where your energy goes, know when your laundry is finished, and keep an eye on individual circuits. Connect supported **SENTRON Powercenter gateways, PAC2200 meters and VersiCharge chargers** to Home Assistant over your local network — without configuring Modbus registers by hand.

**Energy dashboards · Everyday automations · IP-based setup · Local Modbus TCP**

[![Latest release](https://img.shields.io/github/v/release/powerassistant/ha-siemens-sentron)](https://github.com/powerassistant/ha-siemens-sentron/releases/latest)
[![Release ZIP downloads](https://img.shields.io/github/downloads/powerassistant/ha-siemens-sentron/siemens_sentron.zip?displayAssetName=false)](https://github.com/powerassistant/ha-siemens-sentron/releases)
[![Validation status](https://github.com/powerassistant/ha-siemens-sentron/actions/workflows/validate.yml/badge.svg)](https://github.com/powerassistant/ha-siemens-sentron/actions/workflows/validate.yml)
[![HACS Custom](https://img.shields.io/badge/HACS-Custom-41BDF5.svg)](https://my.home-assistant.io/redirect/hacs_repository/?owner=powerassistant&repository=ha-siemens-sentron&category=integration)
[![MIT License](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

[Get started](#get-started) · [Supported devices](#supported-devices) · [Screenshot gallery](docs/SCREENSHOTS.md) · [Technical reference](docs/TECHNICAL_REFERENCE.md)

![Home Assistant Energy dashboard with electricity, solar, battery, gas, water and cost views](https://raw.githubusercontent.com/powerassistant/ha-siemens-sentron/main/docs/screenshots/energy-overview.png)

*Example installation: SENTRON measurements combined within separately configured Home Assistant Energy Dashboard. Dashboard and automations are configured by the user, not installed automatically by this integration.*

## 1. Understand your consumption — electricity, gas and water

**One place to see consumption, compare periods and spot what is driving it.**

Use measured power and cumulative energy for the Home Assistant Energy dashboard, consumption history and reporting. Track grid import and export, compare individual circuits, and see the contribution of larger loads such as EV charging or hot-water production. Combine these readings with your solar and battery integrations for a wider view of your home.

The **PAC2200 universal counter**, exposed as **Counter Configurable**, extends the possibilities beyond electricity: a compatible pulse-output **gas or water meter** can supply consumption pulses through the PAC's digital input. Home Assistant then converts that counter into a correctly scaled gas or water total.

**Important:** Gas and water require a compatible pulse interface, the correct device configuration, and a helper/template with the appropriate unit and statistics metadata. They are not automatically detected as gas or water. A PAC2200 has one digital input and one configurable counter; independent gas and water totals require separate counting channels.

![Live power sources and a hierarchical view of where power is being used](https://raw.githubusercontent.com/powerassistant/ha-siemens-sentron/main/docs/screenshots/power-flow.png)

*From the whole-home view to monitored floors, circuits and individual loads. The illustrated hierarchy is a user-configured Home Assistant view.*

[Set up electricity, gas and water reporting →](docs/ENERGY_DASHBOARD.md)

## 2. “Laundry is finished” — make ordinary appliances smarter

**Your washing machine does not need its own smart-home connection.**

Use the **Power Active** sensor of its monitored circuit to recognize a sustained increase in power when a cycle starts and a sustained return to standby when it finishes. The same approach can be adapted to a tumble dryer or another appliance with a distinguishable power profile.

**Power rises → mark as running → power stays low → notify “Laundry is finished”.**

Send a phone notification, announce the result on a speaker, or update a dashboard indicator through native Home Assistant automations and the corresponding notification or speaker integration.

![Home Assistant automation editor showing power below 3 W for one minute and washing-machine helper actions](https://raw.githubusercontent.com/powerassistant/ha-siemens-sentron/main/docs/screenshots/laundry-automation.png)

*The screenshot illustrates the completion step: below 3 W for one minute, followed by helper changes.*

[Build the start, finish and notification workflow →](docs/AUTOMATIONS.md)

## 3. Enter an IP address. Discover the supported devices.

**No register-by-register setup. No separate manual entry for each Powercenter child device.**

After installation, enter the device's **IP address or hostname** and its Modbus TCP port, normally **502**. The integration identifies the supported root-device type and creates the entities defined for its profile.

With **SENTRON Powercenter 1000, 1100 and 2000**, it also discovers supported, already connected child devices on **unit IDs 1–24**, representing each as a separate Home Assistant device. Standalone **PAC2200** and **VersiCharge** entries use the same setup flow without a child-device scan.

![A Powercenter 1100 with automatically discovered devices named for their circuits and appliances](https://raw.githubusercontent.com/powerassistant/ha-siemens-sentron/main/docs/screenshots/device-discovery.png)

*Gateway and child-device discovery after connecting to the supplied IP address. Circuit names and area assignments are user-defined. Commissioning and pairing devices with the Powercenter remain separate steps; this is not a network-wide IP scan.*

## 4. See more than energy totals

**Understand what is happening on the circuit, not just how much energy it used.**

Depending on the device profile, view current, voltage, active/reactive/apparent power, frequency, power factor, temperature, breaker state, alarms and residual-current monitoring (RCM) values. Add your own alerts for unexpected loads or status changes, and use connection state, radio signal strength, firmware and test information for troubleshooting.

![ECPD circuit monitoring with power, voltage, current, temperature, RCM measurements and status](https://raw.githubusercontent.com/powerassistant/ha-siemens-sentron/main/docs/screenshots/circuit-monitoring.png)

*Available measurements, diagnostics and controls depend on the model, firmware and software profile. See the [full gallery](docs/SCREENSHOTS.md) for PAC2200 measurements, configuration and diagnostics. Screenshot labels have been edited into English for documentation; they are not a guarantee of identical names or defaults in every release.*

> **Monitoring is not electrical protection.** Home Assistant notifications do not replace protective devices, required inspections or qualified commissioning. Write-capable entities are disabled by default. Do not use this integration as a safety-critical control system. Read the [safety and legal notice](DISCLAIMER.md).

## Supported devices

| Connect by IP | Typical use | Discovery |
| --- | --- | --- |
| **SENTRON Powercenter 1000 / 1100 / 2000** | Bring supported communicative SENTRON devices into Home Assistant; especially useful for individual single-phase circuits, breaker states and RCM, depending on the child device | Root type and supported child devices, unit IDs 1–24 |
| **SENTRON PAC2200** | Standalone electrical metering, including three-phase measurements, import/export energy, digital input status and a configurable universal counter | Standalone root device |
| **VersiCharge AC Gen3** | Charging energy, live power, charging state, diagnostics and optional guarded charging controls | Standalone root device |

Use a compatible **Modbus TCP endpoint**. PAC2200 interface variants are not interchangeable, and not every device in a product family exposes the same measurements.

### Supported Powercenter child-device profiles

| Function group | Profiles included |
| --- | --- |
| Circuit monitoring and protection-device status | **5SL6 COM MCB**, **5SL6 COM MCB RCM**, **5SV6 COM AFDD**, **5TY1 COM ECPD** |
| Residual-current monitoring | **5SV8 COM RCM** |
| Auxiliary and fault contacts; remote operating mechanisms | **5ST3 COM AS+FC**, **5ST3 COM RCA Standard**, **5ST3 COM RCA with RCD/IR Test** |
| Motor protection and digital I/O | **3RV2 COM MSP**, **5TT4 COM DIDO** |

A listed profile means software support is present, not that every hardware/firmware combination has been tested. See [known limitations](docs/KNOWN_LIMITATIONS.md) and the [entity model](docs/ENTITY_MODEL.md).

## Get started

Requires **Home Assistant 2026.8.0 or newer** and a reachable, commissioned device with Modbus TCP enabled. Use a stable IP address or DHCP reservation. Keep the connection on a trusted local network; never expose Modbus TCP to the internet.

### Install with HACS

[![Open your Home Assistant instance and add this repository to HACS](https://my.home-assistant.io/badges/hacs_repository.svg)](https://my.home-assistant.io/redirect/hacs_repository/?owner=powerassistant&repository=ha-siemens-sentron&category=integration)

Open **HACS**, find **Siemens SENTRON**, download the latest release and restart Home Assistant. If the repository is not listed, add `https://github.com/powerassistant/ha-siemens-sentron` under **Custom repositories**, with type **Integration**.

### Connect your devices

1. Open **Settings → Devices & services → Add integration → Siemens SENTRON**.
2. Enter the **IP address or hostname**, without `http://` or `https://`, and the **Modbus TCP port**. VersiCharge normally uses unit ID **2**, with **1** tried as a fallback; a different ID can be supplied during setup.
3. Let the integration identify the device and, for a Powercenter, discover supported child devices. Assign meaningful names and areas, then select your sensors for dashboards and automations.

Modbus access and Powercenter device pairing must be set up first. For VersiCharge commissioning, communication settings and operational limits, read the [VersiCharge guide](docs/VERSICHARGE.md).

For manual installation, copy `custom_components/siemens_sentron` into your Home Assistant configuration's `custom_components` directory, restart, and add the integration through the UI.

[Detailed preparation and troubleshooting →](docs/TECHNICAL_REFERENCE.md)

## VersiCharge PV-surplus control

Combine measured charging power and energy with your own solar-surplus automation. Optional power-target, pause/resume and fallback entities are available, but are **disabled by default**. Configure and test the required controls deliberately; the integration does not automatically enable PV-only charging or automatic one-/three-phase switching.

[Read the charging-control guide and its limits →](docs/VERSICHARGE.md)

## Updates, support and documentation

Back up Home Assistant before updating. Existing entity IDs are **not automatically renamed**; review automations before changing IDs manually. The documentation images do not modify your devices, entity names or configuration.

| Task | Guide |
| --- | --- |
| Configure electricity, gas and water totals | [Energy dashboard and reporting](docs/ENERGY_DASHBOARD.md) |
| Detect appliance start/finish and notify | [Everyday automations](docs/AUTOMATIONS.md) |
| Explore all nine screenshots | [Screenshot gallery](docs/SCREENSHOTS.md) |
| Connection, controls, entity IDs and troubleshooting | [Technical reference](docs/TECHNICAL_REFERENCE.md) |
| Device and firmware constraints | [Known limitations](docs/KNOWN_LIMITATIONS.md) |
| Implementation and entity structure | [Architecture](docs/ARCHITECTURE.md) · [Entity model](docs/ENTITY_MODEL.md) |
| Releases and security | [Changelog](CHANGELOG.md) · [Security policy](SECURITY.md) |

Report reproducible problems using the [bug report form](https://github.com/powerassistant/ha-siemens-sentron/issues/new?template=bug_report.yml). Include software versions, device model and firmware, with sanitized logs. Use the [device-support form](https://github.com/powerassistant/ha-siemens-sentron/issues/new?template=device_support.yml) for another model or firmware variant.

The download badge counts release ZIP downloads, including updates and repeats; it does not count unique users or active installations. This is an individual, non-commercial community project with no paid service, support contract, response-time promise or availability commitment.

## License, liability and trademarks

Copyright (c) 2026 powerassistant. The integration is released under the
[MIT License](LICENSE) and provided **AS IS**, without warranty or support
commitment. Mandatory law remains unaffected; no license text can guarantee a
complete exclusion of liability in every jurisdiction. See the
[English legal notice](DISCLAIMER.md), [German summary](DISCLAIMER_DE.md) and
[third-party notice](NOTICE.md).

This is a custom community integration and is not part of Home Assistant Core.
Siemens, SENTRON and Powercenter are trademarks of Siemens AG. Product names identify compatibility and do not by themselves imply
official support or endorsement. Home Assistant is a project of the Open Home
Foundation.
