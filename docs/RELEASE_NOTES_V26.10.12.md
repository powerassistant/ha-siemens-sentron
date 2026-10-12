# Siemens SENTRON V26.10.12

A documentation-focused release bringing the updated SENTRON presentation to HACS.

## Highlights

- Compact, device-first README with the SENTRON panel illustration and supported-device overview.
- Nine English documentation screenshots, an expandable gallery and focused guides for energy reporting, PAC2200 pulse counters and laundry notifications.
- Existing safety, license and trademark notices remain available.

## Compatibility and changes

Requires Home Assistant **2026.8.0 or newer**. Integration Python code, device profiles, Modbus addresses, entity IDs and control defaults are unchanged from **V26.09.10**.

This release includes the dependency change already present on `main`: **`pymodbus>=3.13.1`** instead of `pymodbus==3.13.1`. The automated runtime check targets Home Assistant 2026.8.3, Python 3.14.2 and pymodbus 3.13.1; it does not establish compatibility with every later dependency version.

## Update through HACS

After publication, back up Home Assistant, refresh the Siemens SENTRON repository information in HACS and download/update to **V26.10.12**, then restart Home Assistant. Do not remove or reconfigure existing devices. HACS may keep showing the older README while an older version is selected or installed.

The HACS asset is **`siemens_sentron.zip`**, with `manifest.json` directly at its root. README images and guides remain in the repository at this release tag rather than in the runtime ZIP. Previous releases, tags and assets are preserved.

Monitoring and notifications are not electrical protection. Write-capable entities remain disabled by default; the integration is provided AS IS under the existing MIT license and safety/legal notices.
