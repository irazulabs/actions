from __future__ import annotations

import json
from pathlib import Path

from publish_to_appgallery.cli import main, publish
from publish_to_appgallery.config import load_config

from .conftest import make_config, metadata_runner


def test_config_loads_env_without_eas_input(artifact_path: Path) -> None:
    config = load_config(
        [],
        {
            "PUBLISH_TO_APPGALLERY_ARTIFACT_PATH": str(artifact_path),
            "PUBLISH_TO_APPGALLERY_APP_ID": "123456",
            "PUBLISH_TO_APPGALLERY_CHINESE_MAINLAND_FLAG": "0",
            "PUBLISH_TO_APPGALLERY_DRY_RUN": "true",
        },
    )

    assert config.artifact_path == artifact_path
    assert config.dry_run is True
    assert config.expected_package is None


def test_github_output_file_is_written(artifact_path: Path, tmp_path: Path) -> None:
    output_path = tmp_path / "github-output.txt"
    config = make_config(
        artifact_path,
        dry_run=True,
        expected_package="com.example.app",
        min_version_code=40,
    )

    publish(config, command_runner=metadata_runner(), output_path=output_path)

    outputs = output_path.read_text(encoding="utf-8")
    assert "artifact-file-name=app-release.aab" in outputs
    assert "artifact-sha256=" in outputs
    assert "package-name=com.example.app" in outputs
    assert "version-code=42" in outputs
    assert "dry-run=true" in outputs
    assert "submitted=false" in outputs


def test_cli_dry_run_prints_summary(artifact_path: Path, capsys) -> None:  # type: ignore[no-untyped-def]
    exit_code = main(
        [
            "--artifact-path",
            str(artifact_path),
            "--app-id",
            "123456",
            "--chinese-mainland-flag",
            "0",
            "--dry-run",
        ]
    )

    captured = capsys.readouterr()
    summary = json.loads(captured.out)
    assert exit_code == 0
    assert summary["dryRun"] is True
    assert summary["submitted"] is False
