#!/usr/bin/env python3
"""Validate the release-critical structure without third-party dependencies."""

from __future__ import annotations

import argparse
import json
import re
import struct
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
DOMAIN = "siemens_sentron"
INTEGRATION = ROOT / "custom_components" / DOMAIN
EXPECTED_VERSION = "V26.09.08"
PLACEHOLDER = "REPLACE_WITH_GITHUB_OWNER"


def load_json(path: Path, errors: list[str]) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as err:
        errors.append(f"{path.relative_to(ROOT)}: invalid JSON: {err}")
        return {}
    if not isinstance(value, dict):
        errors.append(f"{path.relative_to(ROOT)}: top-level JSON value must be an object")
        return {}
    return value


def leaf_paths(value: Any, prefix: str = "") -> set[str]:
    if not isinstance(value, dict):
        return {prefix}
    result: set[str] = set()
    for key, child in value.items():
        child_prefix = f"{prefix}.{key}" if prefix else key
        result.update(leaf_paths(child, child_prefix))
    return result


def png_dimensions(path: Path) -> tuple[int, int] | None:
    try:
        data = path.read_bytes()
    except OSError:
        return None
    if len(data) < 24 or data[:8] != b"\x89PNG\r\n\x1a\n":
        return None
    return struct.unpack(">II", data[16:24])


def validate(*, allow_release_gates: bool) -> list[str]:
    errors: list[str] = []
    required_root = [
        ROOT / "README.md",
        ROOT / "hacs.json",
        ROOT / "LICENSE",
        ROOT / "DISCLAIMER.md",
        ROOT / "DISCLAIMER_DE.md",
        ROOT / ".github" / "workflows" / "validate.yml",
        ROOT / "docs" / "KNOWN_LIMITATIONS.md",
        ROOT / "docs" / "images" / "README.md",
    ]
    required_integration = [
        INTEGRATION / "__init__.py",
        INTEGRATION / "binary_sensor.py",
        INTEGRATION / "config_flow.py",
        INTEGRATION / "diagnostics.py",
        INTEGRATION / "manifest.json",
        INTEGRATION / "strings.json",
        INTEGRATION / "versicharge.py",
        INTEGRATION / "translations" / "en.json",
        INTEGRATION / "translations" / "de.json",
        INTEGRATION / "brand" / "icon.png",
    ]
    for path in required_root + required_integration:
        if not path.is_file():
            errors.append(f"missing required file: {path.relative_to(ROOT)}")

    manifest = load_json(INTEGRATION / "manifest.json", errors)
    required_manifest_keys = {
        "codeowners",
        "config_flow",
        "documentation",
        "domain",
        "integration_type",
        "iot_class",
        "issue_tracker",
        "name",
        "version",
    }
    missing_manifest = required_manifest_keys - set(manifest)
    if missing_manifest:
        errors.append(f"manifest.json: missing keys {sorted(missing_manifest)}")
    if manifest.get("domain") != DOMAIN:
        errors.append("manifest.json: domain does not match integration directory")
    if manifest.get("version") != EXPECTED_VERSION:
        errors.append(
            f"manifest.json: expected version {EXPECTED_VERSION!r}, got {manifest.get('version')!r}"
        )
    if manifest.get("integration_type") != "hub":
        errors.append("manifest.json: integration_type must be 'hub'")
    requirements = manifest.get("requirements", [])
    if requirements != ["pymodbus==3.13.1"]:
        errors.append("manifest.json: expected the Home Assistant-compatible pymodbus==3.13.1 pin")

    hacs = load_json(ROOT / "hacs.json", errors)
    if hacs.get("name") != "Siemens SENTRON":
        errors.append("hacs.json: name must be 'Siemens SENTRON'")
    undocumented_hacs_keys = set(hacs) - {
        "content_in_root",
        "country",
        "filename",
        "hacs",
        "hide_default_branch",
        "homeassistant",
        "name",
        "persistent_directory",
        "zip_release",
    }
    if undocumented_hacs_keys:
        errors.append(f"hacs.json: unsupported keys {sorted(undocumented_hacs_keys)}")
    if hacs.get("zip_release"):
        errors.append("hacs.json: zip_release is intentionally not used for the standard layout")

    strings = load_json(INTEGRATION / "strings.json", errors)
    english = load_json(INTEGRATION / "translations" / "en.json", errors)
    german = load_json(INTEGRATION / "translations" / "de.json", errors)
    icons = load_json(INTEGRATION / "icons.json", errors)
    strings_without_title = {key: value for key, value in strings.items() if key != "title"}
    if strings_without_title != english:
        errors.append("strings.json: English source strings do not exactly match translations/en.json")
    if leaf_paths(english) != leaf_paths(german):
        missing_de = sorted(leaf_paths(english) - leaf_paths(german))
        extra_de = sorted(leaf_paths(german) - leaf_paths(english))
        errors.append(
            f"translations/de.json: schema mismatch; missing={missing_de}, extra={extra_de}"
        )

    translated_entities = english.get("entity", {})
    for platform, platform_icons in icons.get("entity", {}).items():
        missing = set(platform_icons) - set(translated_entities.get(platform, {}))
        if missing:
            errors.append(f"icons.json: untranslated {platform} keys {sorted(missing)}")

    icon_size = png_dimensions(INTEGRATION / "brand" / "icon.png")
    if icon_size is None:
        errors.append("brand/icon.png: invalid PNG")
    elif icon_size[0] != icon_size[1] or min(icon_size) < 128:
        errors.append(f"brand/icon.png: expected square icon of at least 128 px, got {icon_size}")

    for path in INTEGRATION.glob("*.py"):
        try:
            compile(path.read_text(encoding="utf-8"), str(path), "exec")
        except (OSError, SyntaxError) as err:
            errors.append(f"{path.relative_to(ROOT)}: Python compile failed: {err}")

    forbidden_extensions = {
        ".7z",
        ".csv",
        ".doc",
        ".docx",
        ".eml",
        ".jpg",
        ".jpeg",
        ".log",
        ".pdf",
        ".ppt",
        ".pptx",
        ".rar",
        ".tsv",
        ".xls",
        ".xlsx",
        ".zip",
    }
    allowed_pngs = {
        INTEGRATION / "brand" / "icon.png",
        INTEGRATION / "brand" / "logo.png",
    }
    for path in ROOT.rglob("*"):
        if path.is_file() and path.suffix.lower() in forbidden_extensions:
            errors.append(f"confidential/source-document file type is not allowed: {path.relative_to(ROOT)}")
        if path.is_file() and path.suffix.lower() == ".png" and path not in allowed_pngs:
            errors.append(f"unapproved image is not allowed: {path.relative_to(ROOT)}")
        if path.is_file() and path.stat().st_size == 0:
            errors.append(f"unexpected empty file: {path.relative_to(ROOT)}")

    source_text = "\n".join(
        path.read_text(encoding="utf-8", errors="replace")
        for path in ROOT.rglob("*")
        if path.is_file() and path.suffix.lower() in {"", ".json", ".md", ".py", ".yml", ".yaml"}
    )
    if not allow_release_gates:
        if PLACEHOLDER in json.dumps(manifest):
            errors.append(f"release gate: replace every {PLACEHOLDER} token")
        if "LICENSE APPROVAL PENDING" in (ROOT / "LICENSE").read_text(
            encoding="utf-8", errors="replace"
        ):
            errors.append("release gate: replace the pending LICENSE with the approved license")

    if "\"slave_address\"" in source_text:
        errors.append("entity terminology: found obsolete slave_address translation/object key")
    if "_attr_translation_key = \"unit_id\"" not in source_text:
        errors.append("entity terminology: unit_id translation key is not wired to an entity")

    button_source = (INTEGRATION / "button.py").read_text(encoding="utf-8")
    disconnect_match = re.search(
        r"class EcpdHardwareDisconnectButtonEntity.*?(?=\nclass |\Z)",
        button_source,
        flags=re.DOTALL,
    )
    if disconnect_match is None:
        errors.append("safety: ECPD permanent-disconnect class was not found")
    else:
        block = disconnect_match.group(0)
        if "_attr_entity_registry_enabled_default = False" not in block:
            errors.append("safety: ECPD permanent disconnect must be disabled by default")
        if "_attr_entity_category = EntityCategory.CONFIG" not in block:
            errors.append("safety: ECPD permanent disconnect must be a Configuration entity")

    return errors


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--allow-release-gates",
        action="store_true",
        help="Allow the intentional owner and license placeholders in a local release candidate.",
    )
    args = parser.parse_args()
    errors = validate(allow_release_gates=args.allow_release_gates)
    if errors:
        print("Repository validation failed:")
        for error in errors:
            print(f"- {error}")
        return 1
    print("Repository validation passed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
