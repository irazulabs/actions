from __future__ import annotations

from pathlib import Path

from publish_to_appgallery.artifact import ArtifactInfo
from publish_to_appgallery.client import PublishResult
from publish_to_appgallery.config import PublishConfig


def _escape_value(value: object | None) -> str:
    if value is None:
        return ""
    return str(value).replace("%", "%25").replace("\n", "%0A").replace("\r", "%0D")


def output_values(
    artifact: ArtifactInfo,
    config: PublishConfig,
    result: PublishResult,
) -> dict[str, object | None]:
    return {
        "artifact-file-name": artifact.file_name,
        "artifact-path": artifact.path,
        "artifact-sha256": artifact.sha256,
        "artifact-size-bytes": artifact.size_bytes,
        "package-name": artifact.metadata.package_name,
        "version-code": artifact.metadata.version_code,
        "dry-run": str(config.dry_run).lower(),
        "object-id": result.object_id,
        "submitted": str(result.submitted).lower(),
    }


def write_github_outputs(
    output_path: Path | None,
    artifact: ArtifactInfo,
    config: PublishConfig,
    result: PublishResult,
) -> None:
    if output_path is None:
        return
    lines = [
        f"{name}={_escape_value(value)}\n"
        for name, value in output_values(artifact, config, result).items()
    ]
    with output_path.open("a", encoding="utf-8") as handle:
        handle.writelines(lines)
