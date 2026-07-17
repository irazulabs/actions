from __future__ import annotations

import uuid
from pathlib import Path

from publish_to_appgallery.artifact import ArtifactInfo
from publish_to_appgallery.client import PublishResult
from publish_to_appgallery.config import PublishConfig


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
    values = {
        name: "" if value is None else str(value)
        for name, value in output_values(artifact, config, result).items()
    }
    value_lines = {line for value in values.values() for line in value.splitlines()}
    delimiter = f"github_output_{uuid.uuid4().hex}"
    while delimiter in value_lines:
        delimiter = f"github_output_{uuid.uuid4().hex}"

    records = "".join(
        f"{name}<<{delimiter}\n{value}\n{delimiter}\n" for name, value in values.items()
    )
    with output_path.open("a", encoding="utf-8", newline="") as handle:
        handle.write(records)
