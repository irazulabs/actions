from __future__ import annotations

import subprocess
from collections.abc import Sequence
from pathlib import Path

import pytest

from publish_to_appgallery.artifact import (
    ArtifactError,
    MetadataInspectionError,
    default_command_runner,
    validate_artifact,
)

from .conftest import make_config, metadata_runner, write_aab


def test_dry_run_validates_aab_without_metadata_requirement(artifact_path: Path) -> None:
    info = validate_artifact(make_config(artifact_path))

    assert info.file_name == "app-release.aab"
    assert info.size_bytes == artifact_path.stat().st_size
    assert len(info.sha256) == 64


def test_non_aab_is_rejected(tmp_path: Path) -> None:
    artifact_path = tmp_path / "app.apk"
    artifact_path.write_bytes(b"not-aab")

    with pytest.raises(ArtifactError, match="Android App Bundle"):
        validate_artifact(make_config(artifact_path))


def test_oversized_aab_is_rejected(artifact_path: Path) -> None:
    with pytest.raises(ArtifactError, match="exceeds"):
        validate_artifact(make_config(artifact_path, max_aab_size_bytes=1))


@pytest.mark.parametrize(
    ("contents", "message"),
    [(b"", "empty"), (b"not-a-zip", "valid ZIP")],
)
def test_invalid_aab_is_rejected(tmp_path: Path, contents: bytes, message: str) -> None:
    artifact_path = tmp_path / "invalid.aab"
    artifact_path.write_bytes(contents)

    with pytest.raises(ArtifactError, match=message):
        validate_artifact(make_config(artifact_path))


def test_corrupt_aab_is_rejected(tmp_path: Path) -> None:
    artifact_path = write_aab(tmp_path / "corrupt.aab")
    contents = bytearray(artifact_path.read_bytes())
    contents[contents.index(b"<manifest />")] ^= 1
    artifact_path.write_bytes(contents)

    with pytest.raises(ArtifactError, match="corrupt ZIP"):
        validate_artifact(make_config(artifact_path))


@pytest.mark.parametrize("missing", ["BundleConfig.pb", "base/manifest/AndroidManifest.xml"])
def test_required_aab_member_is_enforced(tmp_path: Path, missing: str) -> None:
    required = {"BundleConfig.pb", "base/manifest/AndroidManifest.xml"}
    artifact_path = write_aab(tmp_path / "missing.aab", sorted(required - {missing}))

    with pytest.raises(ArtifactError, match=missing):
        validate_artifact(make_config(artifact_path))


def test_long_filename_is_rejected(tmp_path: Path) -> None:
    artifact_path = tmp_path / ("a" * 253 + ".aab")

    with pytest.raises(ArtifactError, match="256"):
        validate_artifact(make_config(artifact_path))


def test_bundle_metadata_validation_uses_bundletool_jar(
    artifact_path: Path, tmp_path: Path
) -> None:
    calls: list[list[str]] = []
    bundletool_jar = tmp_path / "bundletool.jar"

    def run(args: Sequence[str]) -> subprocess.CompletedProcess[str]:
        calls.append(list(args))
        stdout = "42" if "/manifest/@android:versionCode" in args else "com.example.app"
        return subprocess.CompletedProcess(args=list(args), returncode=0, stdout=stdout, stderr="")

    config = make_config(
        artifact_path,
        bundletool_jar=bundletool_jar,
        expected_package="com.example.app",
        min_version_code=40,
    )
    bundletool_jar.write_bytes(b"jar")

    info = validate_artifact(config, command_runner=run)

    assert info.metadata.package_name == "com.example.app"
    assert info.metadata.version_code == 42
    assert calls[0][:3] == ["java", "-jar", str(tmp_path / "bundletool.jar")]


def test_explicit_bundletool_jar_must_be_a_file(artifact_path: Path, tmp_path: Path) -> None:
    config = make_config(artifact_path, bundletool_jar=tmp_path / "missing.jar")

    with pytest.raises(ArtifactError, match="JAR path is not a file"):
        validate_artifact(config)


def test_default_runner_hides_secrets_and_times_out(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured: dict[str, object] = {}

    def run(args: Sequence[str], **kwargs: object) -> subprocess.CompletedProcess[str]:
        captured.update(kwargs)
        return subprocess.CompletedProcess(args=list(args), returncode=0, stdout="", stderr="")

    for name in (
        "SERVICE_ACCOUNT_JSON",
        "CLIENT_SECRET",
        "PUBLISH_TO_APPGALLERY_SERVICE_ACCOUNT_JSON",
        "PUBLISH_TO_APPGALLERY_CLIENT_SECRET",
    ):
        monkeypatch.setenv(name, "secret")
    monkeypatch.setenv("PATH", "kept")
    monkeypatch.setattr(subprocess, "run", run)

    default_command_runner(["bundletool"])

    env = captured["env"]
    assert isinstance(env, dict)
    assert env["PATH"] == "kept"
    assert "SERVICE_ACCOUNT_JSON" not in env
    assert "CLIENT_SECRET" not in env
    assert "PUBLISH_TO_APPGALLERY_SERVICE_ACCOUNT_JSON" not in env
    assert "PUBLISH_TO_APPGALLERY_CLIENT_SECRET" not in env
    assert captured["timeout"] == 60


def test_requested_metadata_fails_when_inspection_fails(artifact_path: Path) -> None:
    def run(_args: Sequence[str]) -> subprocess.CompletedProcess[str]:
        raise FileNotFoundError("bundletool")

    config = make_config(artifact_path, expected_package="com.example.app")

    with pytest.raises(MetadataInspectionError, match="metadata inspection is required"):
        validate_artifact(config, command_runner=run)


def test_optional_metadata_tolerates_executable_failure(artifact_path: Path) -> None:
    def run(_args: Sequence[str]) -> subprocess.CompletedProcess[str]:
        raise PermissionError("bundletool is not executable")

    info = validate_artifact(make_config(artifact_path), command_runner=run)

    assert info.metadata.inspection_error == "bundletool is not executable"


def test_package_mismatch_is_rejected(artifact_path: Path) -> None:
    config = make_config(artifact_path, expected_package="com.example.app")

    with pytest.raises(ArtifactError, match="Expected package"):
        validate_artifact(config, command_runner=metadata_runner("com.other.app"))
