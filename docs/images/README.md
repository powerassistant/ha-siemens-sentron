# Screenshot replacement checklist

The three SVG files in this directory are deliberate placeholders, not simulated
Home Assistant results. Replace them only with captures from a real test
installation.

## Requested captures

1. **Integration setup** — the Siemens SENTRON config flow before submission;
   use a documentation-only host such as `sentron.local` instead of a real IP.
2. **Device overview** — one Powercenter with automatically discovered child
   devices, or one PAC2200 device page.
3. **Energy Dashboard** — a suitable active-energy entity added to the Home
   Assistant Energy Dashboard.

## Publication checks

- Use a consistent Home Assistant theme and crop ratio, preferably 16:9 at
  1200 px width or greater.
- Remove or mask IP addresses, host names, MAC addresses, serial numbers, site
  and area names, user names, location data and customer-specific values.
- Do not include manufacturer manuals, register maps, internal web interfaces
  or other third-party content unless its separate publication right is
  documented.
- Confirm that every displayed entity and value comes from a safe test
  installation and cannot identify a real facility.
- Record who created the capture and the publication approval in the release
  checklist.
- Have the repository validator explicitly approve the final image paths before
  publishing them. Its default is to reject unreviewed raster images.

The maintainer can then replace the README links with the approved PNG or WebP
files. Until that review is complete, keep the labelled SVG placeholders.
