# Contributing

Contributions are welcome after the repository has been approved for public release.

## Before opening a change

1. Open an issue describing the device, firmware and intended behavior.
2. Base register changes only on documentation that may legally be used for an open-source implementation.
3. Do not upload Siemens-internal or classified documents, register maps,
   manufacturer-document screenshots, unsanitized logs, customer data, serial
   numbers or network addresses. Home Assistant UI screenshots must follow
   `docs/images/README.md` and have documented publication rights.
4. Preserve the device separation described in `docs/ARCHITECTURE.md`.
5. Preserve the naming and category rules in `docs/ENTITY_MODEL.md`.

## Rights and sign-off

Every commit must be signed off with `git commit -s`. By adding the
`Signed-off-by` line, the contributor certifies the
[Developer Certificate of Origin 1.1](https://developercertificate.org/),
including that they have the right to submit the contribution under this
project's MIT License. Do not contribute work copied from confidential,
employer-owned or third-party material without written authorization.

## Validation

Run the repository checks before opening a pull request:

```bash
python3 scripts/validate_repository.py
python3 -m compileall -q custom_components/siemens_sentron
```

GitHub Actions also run HACS validation and Hassfest. Pull requests must pass all checks without ignored HACS rules.

## Hardware changes

State the exact device family and firmware tested. For write commands, document the physical result, readback result, failure behavior and recovery procedure. Test hazardous operations only on an appropriately isolated installation by qualified personnel.
