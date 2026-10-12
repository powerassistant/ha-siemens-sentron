# Siemens SENTRON for Home Assistant

**Your SENTRON devices. Connected to Home Assistant.**

![Communicative SENTRON devices in an electrical distribution panel](https://raw.githubusercontent.com/powerassistant/ha-siemens-sentron/main/docs/images/sentron-panel.webp)

Bring **SENTRON Powercenter 1000 / 1100 / 2000**, their supported communicative devices and standalone **PAC2200** meters into Home Assistant. Access measurements, device states, diagnostics and supported controls over **local Modbus TCP** — with IP-based setup and automatic device identification.

[![Latest release](https://img.shields.io/github/v/release/powerassistant/ha-siemens-sentron)](https://github.com/powerassistant/ha-siemens-sentron/releases/latest)
[![Release ZIP downloads](https://img.shields.io/github/downloads/powerassistant/ha-siemens-sentron/siemens_sentron.zip?displayAssetName=false)](https://github.com/powerassistant/ha-siemens-sentron/releases)
[![Validation](https://github.com/powerassistant/ha-siemens-sentron/actions/workflows/validate.yml/badge.svg)](https://github.com/powerassistant/ha-siemens-sentron/actions/workflows/validate.yml)
[![HACS Custom](https://img.shields.io/badge/HACS-Custom-41BDF5.svg)](https://my.home-assistant.io/redirect/hacs_repository/?owner=powerassistant&repository=ha-siemens-sentron&category=integration)
[![MIT License](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

[Supported devices](#supported-devices) · [Use cases](#what-you-can-do) · [Get started](#get-started) · [Screenshots](docs/SCREENSHOTS.md)

## Supported devices

### Via SENTRON Powercenter 1000 / 1100 / 2000

| Devices | Integration capabilities |
| --- | --- |
| **5SL6 COM MCB**, **5SL6 COM MCB RCM**, **5SV6 COM AFDD**, **5TY1 COM ECPD** | Single-phase circuit measurements, energy where available, breaker states; RCM and controls where supported |
| **5SV8 COM RCM** | Residual-current monitoring and diagnostics |
| **5ST3 COM AS+FC**, **5ST3 COM RCA Standard**, **5ST3 COM RCA with RCD/IR Test** | Contact/switching status and supported remote-operation functions |
| **3RV2 COM MSP**, **5TT4 COM DIDO** | Motor-protection device status/diagnostics and digital I/O, respectively |

**One gateway entry, separate Home Assistant devices.** Supported, already paired child devices are discovered automatically on unit IDs **1–24**. Pairing and commissioning happen beforehand; discovery is not a network-wide scan.

### Standalone, directly over Modbus TCP

**SENTRON PAC2200** — three-phase measurements, import/export energy, digital input and configurable universal counter.

**VersiCharge AC Gen3** — charging power, energy, status and optional charging controls. [Charging guide →](docs/VERSICHARGE.md)

Capabilities depend on the device profile and firmware; not every hardware/firmware combination is physically validated. A compatible Modbus TCP interface is required. [Compatibility & limits →](docs/KNOWN_LIMITATIONS.md)

<details>
<summary><strong>See device discovery and circuit measurements</strong></summary>

![Powercenter 1100 with individually named devices and circuits](https://raw.githubusercontent.com/powerassistant/ha-siemens-sentron/main/docs/screenshots/device-discovery.png)

![ECPD electrical measurements, RCM values and device status](https://raw.githubusercontent.com/powerassistant/ha-siemens-sentron/main/docs/screenshots/circuit-monitoring.png)

</details>

## What you can do

| Use case | From SENTRON data to practical value |
| --- | --- |
| **Energy monitoring & reporting** | Track grid import/export and individual loads. Use power and energy readings in your dashboards alongside solar/battery integrations. [Setup →](docs/ENERGY_DASHBOARD.md) |
| **Gas & water metering** | Feed compatible meter pulses into the PAC2200 **Counter Configurable**. A helper/template supplies volume scaling, units and statistics metadata. One PAC2200 has one counting channel; independent gas/water totals need separate channels. [Guide →](docs/ENERGY_DASHBOARD.md) |
| **“Laundry is finished”** | Use **Power Active** to detect a sustained cycle start and return to standby, then notify a phone or speaker. Require a running state before detecting completion; tune thresholds/delays to the appliance. [Example →](docs/AUTOMATIONS.md) |
| **Condition monitoring & remote control** | Follow breaker states, residual currents, temperatures and diagnostics. Create alerts and use supported switching/configuration or VersiCharge charging controls after deliberately enabling and testing them. [Controls →](docs/TECHNICAL_REFERENCE.md#write-controls-and-operational-safety) |

**The integration supplies device data and supported controls.** Dashboards, notifications and automations are configured in Home Assistant, not installed automatically.

<details>
<summary><strong>See energy reporting and a laundry automation</strong></summary>

![Example energy overview combining SENTRON readings with other Home Assistant sources](https://raw.githubusercontent.com/powerassistant/ha-siemens-sentron/main/docs/screenshots/energy-overview.png)

![Example laundry-completion trigger and helper actions](https://raw.githubusercontent.com/powerassistant/ha-siemens-sentron/main/docs/screenshots/laundry-automation.png)

The automation capture shows the completion step, not the full start/notification workflow. Its below-3-W-for-one-minute setting is appliance-specific. Screenshot labels were edited into English and may differ from your installation.

[All screenshots →](docs/SCREENSHOTS.md)

</details>

## Get started

Requires **Home Assistant 2026.8.0+**, commissioned devices with Modbus TCP enabled, and a stable IP address or hostname.

[![Add this repository to HACS](https://my.home-assistant.io/badges/hacs_repository.svg)](https://my.home-assistant.io/redirect/hacs_repository/?owner=powerassistant&repository=ha-siemens-sentron&category=integration)

1. **Install:** Download **Siemens SENTRON** through HACS and restart Home Assistant. If not listed, add `https://github.com/powerassistant/ha-siemens-sentron` as a custom repository of type **Integration**.
2. **Connect:** Open **Settings → Devices & services → Add integration → Siemens SENTRON**. Enter the IP address/hostname and TCP port, normally **502**.
3. **Use:** Let discovery finish, assign device names/areas, and select the entities for your dashboards or automations.

[Manual installation & troubleshooting](docs/TECHNICAL_REFERENCE.md) · [Entity model](docs/ENTITY_MODEL.md) · [Architecture](docs/ARCHITECTURE.md) · [Changelog](CHANGELOG.md)

## Safety, support & license

> **Monitoring is not electrical protection.** This integration is not a safety function or billing meter and does not replace protective devices, inspections or qualified commissioning. Write-capable entities are disabled by default; test before use. The ECPD permanent-disconnect command can be irreversible. A Home Assistant state is not proof that a circuit is safe to work on. Keep Modbus on a trusted, access-controlled local network — never expose it to the internet.

Back up Home Assistant before updates; existing entity IDs are preserved. [Report an issue](https://github.com/powerassistant/ha-siemens-sentron/issues/new?template=bug_report.yml) with versions, device details and sanitized logs. [Security policy](SECURITY.md). Download counts include updates/repeats, not unique installations.

This is an individual, non-commercial community project, not Home Assistant Core, with no paid service, support contract, response-time promise or availability commitment.

Copyright (c) 2026 powerassistant. Released under the **[MIT License](LICENSE)**, **AS IS**, without warranty or support commitment. Mandatory law remains unaffected; no license text guarantees complete exclusion of liability in every jurisdiction. [Full legal notice](DISCLAIMER.md) · [German summary](DISCLAIMER_DE.md) · [Third-party notice](NOTICE.md).

Siemens, SENTRON and Powercenter are trademarks of Siemens AG. Product names identify compatibility, not official support or endorsement. Home Assistant is a project of the Open Home Foundation.
