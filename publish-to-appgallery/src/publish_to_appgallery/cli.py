from __future__ import annotations

import json
import os
import sys
from collections.abc import Sequence
from pathlib import Path

from publish_to_appgallery.artifact import ArtifactInfo, CommandRunner, validate_artifact
from publish_to_appgallery.client import HuaweiClient, PublishResult, Sleeper, Transport
from publish_to_appgallery.config import PublishConfig, load_config
from publish_to_appgallery.outputs import write_github_outputs


def _planned_operations(config: PublishConfig, artifact: ArtifactInfo) -> list[str]:
    return [
        f"GET /publish/v2/upload-url/for-obs for {artifact.file_name}",
        f"PUT signed OBS upload URL for {artifact.file_name}",
        f"PUT /publish/v2/app-file-info with fileType=5 for {artifact.file_name}",
        f"wait {config.parse_wait_seconds}s for Huawei package parsing",
        "POST /publish/v2/app-submit releaseType=1",
    ]


def _summary(
    config: PublishConfig,
    artifact: ArtifactInfo,
    result: PublishResult,
) -> dict[str, object]:
    return {
        "artifact": {
            "fileName": artifact.file_name,
            "path": str(artifact.path),
            "sha256": artifact.sha256,
            "sizeBytes": artifact.size_bytes,
            "packageName": artifact.metadata.package_name,
            "versionCode": artifact.metadata.version_code,
        },
        "dryRun": config.dry_run,
        "objectId": result.object_id,
        "operations": _planned_operations(config, artifact),
        "submitted": result.submitted,
    }


def publish(
    config: PublishConfig,
    *,
    command_runner: CommandRunner | None = None,
    output_path: Path | None = None,
    sleeper: Sleeper | None = None,
    transport: Transport | None = None,
) -> dict[str, object]:
    artifact = validate_artifact(
        config,
        command_runner=command_runner if command_runner is not None else None,
    )
    result = (
        PublishResult(object_id=None, submitted=False)
        if config.dry_run
        else HuaweiClient(
            config,
            transport=transport if transport is not None else None,
            sleeper=sleeper if sleeper is not None else None,
        ).publish(artifact)
    )
    summary = _summary(config, artifact, result)
    write_github_outputs(output_path, artifact, config, result)
    return summary


def _github_output_path() -> Path | None:
    value = os.environ.get("GITHUB_OUTPUT")
    return Path(value) if value else None


def main(argv: Sequence[str] | None = None) -> int:
    try:
        config = load_config(argv)
        summary = publish(config, output_path=_github_output_path())
    except Exception as exc:  # noqa: BLE001 - CLI should turn all failures into readable output.
        print(str(exc), file=sys.stderr)
        return 1

    print(json.dumps(summary, indent=2, sort_keys=True))
    return 0
