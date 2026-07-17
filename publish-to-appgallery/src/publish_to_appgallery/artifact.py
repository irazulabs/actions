from __future__ import annotations

import hashlib
import os
import subprocess
import zipfile
import zlib
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from pathlib import Path

from publish_to_appgallery.config import PublishConfig


class ArtifactError(ValueError):
    """Raised when an Android App Bundle cannot be accepted for publishing."""


class MetadataInspectionError(RuntimeError):
    """Raised when bundle metadata inspection is required but unavailable."""


@dataclass(frozen=True)
class BundleMetadata:
    package_name: str | None = None
    version_code: int | None = None
    inspection_error: str | None = None


@dataclass(frozen=True)
class ArtifactInfo:
    path: Path
    file_name: str
    size_bytes: int
    sha256: str
    metadata: BundleMetadata


CommandRunner = Callable[[Sequence[str]], subprocess.CompletedProcess[str]]


def default_command_runner(args: Sequence[str]) -> subprocess.CompletedProcess[str]:
    env = os.environ.copy()
    for name in (
        "SERVICE_ACCOUNT_JSON",
        "CLIENT_SECRET",
        "PUBLISH_TO_APPGALLERY_SERVICE_ACCOUNT_JSON",
        "PUBLISH_TO_APPGALLERY_CLIENT_SECRET",
    ):
        env.pop(name, None)
    return subprocess.run(
        args,
        capture_output=True,
        check=True,
        env=env,
        text=True,
        timeout=60,
    )


def calculate_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _validate_bundle_archive(path: Path) -> None:
    required_members = {"BundleConfig.pb", "base/manifest/AndroidManifest.xml"}
    try:
        with zipfile.ZipFile(path) as archive:
            members = set(archive.namelist())
            corrupt_member = archive.testzip()
    except (zipfile.BadZipFile, EOFError, OSError, RuntimeError, zlib.error) as exc:
        raise ArtifactError(f"AAB is not a valid ZIP archive: {path}") from exc

    if corrupt_member is not None:
        raise ArtifactError(f"AAB contains a corrupt ZIP member: {corrupt_member}")
    if missing := required_members - members:
        raise ArtifactError(f"AAB is missing required members: {', '.join(sorted(missing))}")


def _strip_bundletool_output(value: str) -> str | None:
    stripped = value.strip().strip('"')
    return stripped or None


def _read_bundle_attribute(
    artifact_path: Path,
    xpath: str,
    bundletool_jar: Path | None,
    command_runner: CommandRunner,
) -> str | None:
    if bundletool_jar is not None:
        args = [
            "java",
            "-jar",
            str(bundletool_jar),
            "dump",
            "manifest",
            "--bundle",
            str(artifact_path),
            "--xpath",
            xpath,
        ]
    else:
        args = [
            "bundletool",
            "dump",
            "manifest",
            "--bundle",
            str(artifact_path),
            "--xpath",
            xpath,
        ]

    result = command_runner(args)
    return _strip_bundletool_output(result.stdout)


def inspect_bundle_metadata(
    artifact_path: Path,
    bundletool_jar: Path | None,
    command_runner: CommandRunner | None = None,
) -> BundleMetadata:
    runner = command_runner or default_command_runner
    try:
        package_name = _read_bundle_attribute(
            artifact_path,
            "/manifest/@package",
            bundletool_jar,
            runner,
        )
        version_code_text = _read_bundle_attribute(
            artifact_path,
            "/manifest/@android:versionCode",
            bundletool_jar,
            runner,
        )
    except (OSError, subprocess.CalledProcessError, subprocess.TimeoutExpired) as exc:
        return BundleMetadata(inspection_error=str(exc))

    version_code = (
        int(version_code_text) if version_code_text and version_code_text.isdigit() else None
    )
    return BundleMetadata(package_name=package_name, version_code=version_code)


def validate_artifact(
    config: PublishConfig,
    command_runner: CommandRunner | None = None,
) -> ArtifactInfo:
    path = config.artifact_path.resolve()
    if path.suffix.lower() != ".aab":
        raise ArtifactError(f"Expected an Android App Bundle (.aab), received {path}.")
    if len(path.name) > 256:
        raise ArtifactError("AAB filename must be 256 characters or fewer.")
    if not path.is_file():
        raise ArtifactError(f"Artifact path is not a file: {path}")

    size_bytes = path.stat().st_size
    if size_bytes == 0:
        raise ArtifactError("AAB is empty.")
    if size_bytes > config.max_aab_size_bytes:
        raise ArtifactError(
            f"AAB is {size_bytes} bytes, which exceeds the configured "
            f"{config.max_aab_size_bytes} byte limit."
        )
    _validate_bundle_archive(path)

    if config.bundletool_jar is not None and not config.bundletool_jar.is_file():
        raise ArtifactError(f"bundletool JAR path is not a file: {config.bundletool_jar}")

    metadata_required = config.expected_package is not None or config.min_version_code is not None
    metadata = inspect_bundle_metadata(path, config.bundletool_jar, command_runner)
    if metadata.inspection_error and metadata_required:
        raise MetadataInspectionError(
            f"Bundle metadata inspection is required but failed: {metadata.inspection_error}"
        )

    if config.expected_package is not None and metadata.package_name != config.expected_package:
        raise ArtifactError(
            f"Expected package {config.expected_package}, but artifact declares "
            f"{metadata.package_name or 'unknown'}."
        )
    if config.min_version_code is not None:
        if metadata.version_code is None:
            raise ArtifactError("Expected versionCode metadata, but none was available.")
        if metadata.version_code < config.min_version_code:
            raise ArtifactError(
                f"Expected versionCode >= {config.min_version_code}, "
                f"but artifact declares {metadata.version_code}."
            )

    return ArtifactInfo(
        path=path,
        file_name=path.name,
        size_bytes=size_bytes,
        sha256=calculate_sha256(path),
        metadata=metadata,
    )
