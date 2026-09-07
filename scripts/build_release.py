#!/usr/bin/env python3
"""Build the flat integration ZIP used by HACS release downloads."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import zipfile


ROOT = Path(__file__).resolve().parents[1]
INTEGRATION = ROOT / "custom_components" / "siemens_sentron"
SUPPORTED_SUFFIXES = {".py", ".json", ".png"}
REQUIRED_FILES = {
    "__init__.py",
    "config_flow.py",
    "manifest.json",
    "strings.json",
    "translations/de.json",
    "translations/en.json",
    "brand/icon.png",
    "brand/logo.png",
}


def _package_files(directory: Path) -> list[Path]:
    """Collect runtime files without following symlinks or including caches."""
    files: list[Path] = []
    for path in sorted(directory.iterdir()):
        if path.is_symlink():
            raise ValueError(f"Symlinks are not allowed in release packages: {path}")
        if path.name.startswith(".") or path.name == "__pycache__":
            continue
        if path.is_dir():
            files.extend(_package_files(path))
        elif path.is_file() and path.suffix in SUPPORTED_SUFFIXES:
            files.append(path)
    return files


def build_release(
    tag: str, output: Path, integration_dir: Path = INTEGRATION
) -> Path:
    """Create a deterministic archive, requiring an exact manifest/tag match."""
    integration_dir = Path(integration_dir)
    output = Path(output)
    if integration_dir.is_symlink():
        raise ValueError("The integration directory must not be a symlink")
    if not integration_dir.is_dir():
        raise ValueError(f"Integration directory does not exist: {integration_dir}")
    if output.exists() or output.is_symlink():
        raise FileExistsError(f"Refusing to overwrite an existing archive: {output}")

    files = _package_files(integration_dir)
    names = {path.relative_to(integration_dir).as_posix() for path in files}
    missing = REQUIRED_FILES - names
    if missing:
        raise ValueError(f"Missing required package files: {', '.join(sorted(missing))}")

    manifest = json.loads((integration_dir / "manifest.json").read_text("utf-8"))
    if not isinstance(manifest, dict) or manifest.get("domain") != "siemens_sentron":
        raise ValueError("Release manifest must have domain 'siemens_sentron'")
    if not tag or manifest.get("version") != tag:
        raise ValueError(
            f"Release tag {tag!r} must exactly match manifest version "
            f"{manifest.get('version')!r}"
        )

    # Read and validate all inputs before creating the output file.
    contents = sorted(
        (path.relative_to(integration_dir).as_posix(), path.read_bytes())
        for path in files
    )
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("xb") as destination:
        try:
            with zipfile.ZipFile(destination, "w", compression=zipfile.ZIP_DEFLATED) as archive:
                for name, data in contents:
                    info = zipfile.ZipInfo(name, date_time=(1980, 1, 1, 0, 0, 0))
                    info.create_system = 3
                    info.external_attr = 0o100644 << 16
                    info.compress_type = zipfile.ZIP_DEFLATED
                    archive.writestr(info, data, compresslevel=9)
        except BaseException:
            # Never leave a partial file that could be mistaken for a release.
            destination.close()
            output.unlink(missing_ok=True)
            raise
    return output


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--tag", required=True, help="Exact published GitHub release tag")
    parser.add_argument("--output", required=True, type=Path, help="New integration ZIP path")
    args = parser.parse_args()
    try:
        output = build_release(args.tag, args.output)
    except (OSError, ValueError) as err:
        parser.exit(1, f"Release packaging failed: {err}\n")
    print(f"Built {output} for release {args.tag}")


if __name__ == "__main__":
    main()
