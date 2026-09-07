"""Check that release assets install correctly through HACS ZIP extraction."""

from __future__ import annotations

import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
import zipfile


ROOT = Path(__file__).resolve().parents[1]
INTEGRATION = ROOT / "custom_components" / "siemens_sentron"
SPEC = importlib.util.spec_from_file_location(
    "sentron_release_package", ROOT / "scripts" / "build_release.py"
)
if SPEC is None or SPEC.loader is None:
    raise RuntimeError("Could not load build_release.py")
PACKAGE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(PACKAGE)


class ReleasePackageTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.directory = Path(self.temporary.name)
        self.integration = self.directory / "integration"
        self.integration.mkdir()
        self.output = self.directory / "siemens_sentron.zip"
        self.tag = "V26.09.10"
        self.manifest = {"domain": "siemens_sentron", "version": self.tag}
        for name in (
            "__init__.py", "config_flow.py", "strings.json",
            "translations/de.json", "translations/en.json",
            "brand/icon.png", "brand/logo.png",
        ):
            self.write(name, "{}" if name.endswith(".json") else "fixture")
        self.write("manifest.json", json.dumps(self.manifest))

    def write(self, name: str, content: str) -> Path:
        path = self.integration / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
        return path

    def build(self, tag: str | None = None) -> Path:
        return PACKAGE.build_release(tag or self.tag, self.output, self.integration)

    def test_real_integration_extracts_with_manifest_and_assets_at_expected_paths(self) -> None:
        manifest = json.loads((INTEGRATION / "manifest.json").read_text("utf-8"))
        PACKAGE.build_release(manifest["version"], self.output, INTEGRATION)
        with zipfile.ZipFile(self.output) as archive:
            self.assertIsNone(archive.testzip())
            self.assertEqual(json.loads(archive.read("manifest.json")), manifest)
            for name in (
                "__init__.py", "config_flow.py", "coordinator.py", "strings.json",
                "translations/de.json", "translations/en.json",
                "brand/icon.png", "brand/logo.png",
            ):
                self.assertEqual(archive.read(name), (INTEGRATION / name).read_bytes())
            self.assertFalse(any(name.startswith("custom_components/") for name in archive.namelist()))
            installed = self.directory / "installed" / "custom_components" / "siemens_sentron"
            archive.extractall(installed)
        self.assertTrue((installed / "manifest.json").is_file())
        self.assertTrue((installed / "brand" / "logo.png").is_file())

    def test_tag_must_match_the_entire_manifest_version(self) -> None:
        for tag in ("26.09.10", "v26.09.10", "V26.09.1", "V26.09.10-extra"):
            with self.subTest(tag=tag):
                with self.assertRaisesRegex(ValueError, "exactly match"):
                    self.build(tag)
                self.assertFalse(self.output.exists())

    def test_missing_runtime_file_prevents_an_archive(self) -> None:
        (self.integration / "config_flow.py").unlink()
        with self.assertRaisesRegex(ValueError, "config_flow.py"):
            self.build()
        self.assertFalse(self.output.exists())

    def test_excludes_bytecode_hidden_files_and_unsupported_files(self) -> None:
        excluded = (
            "__pycache__/module.cpython-311.pyc", "__pycache__/stray.py",
            "module.pyc", ".DS_Store", ".hidden.json", ".git/config.json",
            "translations/.backup.json", "scratch.txt",
        )
        for name in excluded:
            self.write(name, "must not ship")
        self.build()
        with zipfile.ZipFile(self.output) as archive:
            for name in excluded:
                self.assertNotIn(name, archive.namelist())

    def test_symlink_file_or_directory_is_rejected_before_writing(self) -> None:
        outside = self.directory / "outside"
        outside.mkdir()
        secret = outside / "secret.json"
        secret.write_text("outside content", encoding="utf-8")
        for name, target in (("linked.json", secret), ("linked", outside)):
            with self.subTest(name=name):
                link = self.integration / name
                link.symlink_to(target, target_is_directory=target.is_dir())
                try:
                    with self.assertRaisesRegex(ValueError, "Symlinks"):
                        self.build()
                    self.assertFalse(self.output.exists())
                finally:
                    link.unlink()

    def test_symlink_integration_root_is_rejected(self) -> None:
        link = self.directory / "linked-integration"
        link.symlink_to(self.integration, target_is_directory=True)
        with self.assertRaisesRegex(ValueError, "symlink"):
            PACKAGE.build_release(self.tag, self.output, link)
        self.assertFalse(self.output.exists())

    def test_deterministic_archive_ignores_source_mtime_and_permissions(self) -> None:
        self.build()
        first = self.output.read_bytes()
        self.output.unlink()
        for source in self.integration.rglob("*"):
            if source.is_file():
                os.utime(source, (1700000000, 1700000000))
                source.chmod(0o600)
        self.build()
        self.assertEqual(self.output.read_bytes(), first)

    def test_existing_archive_is_preserved(self) -> None:
        self.output.write_bytes(b"existing asset")
        with self.assertRaises(FileExistsError):
            self.build()
        self.assertEqual(self.output.read_bytes(), b"existing asset")

    def test_cli_rejects_mismatched_tag_without_creating_output(self) -> None:
        result = subprocess.run(
            [sys.executable, str(ROOT / "scripts" / "build_release.py"),
             "--tag", "definitely-wrong", "--output", str(self.output)],
            capture_output=True, text=True, check=False,
        )
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("exactly match", result.stderr)
        self.assertFalse(self.output.exists())


if __name__ == "__main__":
    unittest.main()
