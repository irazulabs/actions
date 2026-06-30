from __future__ import annotations

import subprocess
from collections.abc import Sequence
from pathlib import Path

import pytest

from publish_to_appgallery.artifact import ArtifactError, MetadataInspectionError, validate_artifact

from .conftest import make_config, metadata_runner


def test_dry_run_validates_aab_without_metadata_requirement(artifact_path: Path) -> None:
    info = validate_artifact(make_config(artifact_path))

    assert info.file_name == "app-release.aab"
    assert info.size_bytes == len(b"fake-aab-content")
    assert len(info.sha256) == 64


def test_non_aab_is_rejected(tmp_path: Path) -> None:
    artifact_path = tmp_path / "app.apk"
    artifact_path.write_bytes(b"not-aab")

    with pytest.raises(ArtifactError, match="Android App Bundle"):
        validate_artifact(make_config(artifact_path))


def test_oversized_aab_is_rejected(artifact_path: Path) -> None:
    with pytest.raises(ArtifactError, match="exceeds"):
        validate_artifact(make_config(artifact_path, max_aab_size_bytes=1))


def test_bundle_metadata_validation_uses_bundletool_jar(
    artifact_path: Path, tmp_path: Path
) -> None:
    calls: list[list[str]] = []

    def run(args: Sequence[str]) -> subprocess.CompletedProcess[str]:
        calls.append(list(args))
        stdout = "42" if "/manifest/@android:versionCode" in args else "com.example.app"
        return subprocess.CompletedProcess(args=list(args), returncode=0, stdout=stdout, stderr="")

    config = make_config(
        artifact_path,
        bundletool_jar=tmp_path / "bundletool.jar",
        expected_package="com.example.app",
        min_version_code=40,
    )

    info = validate_artifact(config, command_runner=run)

    assert info.metadata.package_name == "com.example.app"
    assert info.metadata.version_code == 42
    assert calls[0][:3] == ["java", "-jar", str(tmp_path / "bundletool.jar")]


def test_requested_metadata_fails_when_inspection_fails(artifact_path: Path) -> None:
    def run(_args: Sequence[str]) -> subprocess.CompletedProcess[str]:
        raise FileNotFoundError("bundletool")

    config = make_config(artifact_path, expected_package="com.example.app")

    with pytest.raises(MetadataInspectionError, match="metadata inspection is required"):
        validate_artifact(config, command_runner=run)


def test_package_mismatch_is_rejected(artifact_path: Path) -> None:
    config = make_config(artifact_path, expected_package="com.example.app")

    with pytest.raises(ArtifactError, match="Expected package"):
        validate_artifact(config, command_runner=metadata_runner("com.other.app"))
