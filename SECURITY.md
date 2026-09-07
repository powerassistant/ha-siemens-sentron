# Security policy

## Reporting a vulnerability

Do not disclose a security vulnerability in a public issue. Use the repository's private GitHub Security Advisory form. Include the affected version, impact, reproduction steps and any mitigation without sharing credentials, customer information or classified product documents.

## Network and operational scope

The integration communicates through Modbus TCP, which does not provide authentication or encryption. Deploy the devices on a trusted, segmented network and never expose TCP port 502 directly to the internet.

Some entities issue physical switching, test, configuration or permanent-disconnect commands. Home Assistant access control, network segmentation and device commissioning remain the operator's responsibility. The integration must not be used as a safety function, protection layer, lockout/tagout indicator, billing meter or legally required measurement system.

Supported security fixes are published for the latest released version only.

