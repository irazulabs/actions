from __future__ import annotations

import json
from pathlib import Path

import pytest

from publish_to_appgallery.cli import main, publish
from publish_to_appgallery.config import DEFAULT_DOMAIN, ReleaseMode, load_config

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
    assert config.release_mode is ReleaseMode.PRODUCTION


def _config_env(artifact_path: Path, **overrides: str) -> dict[str, str]:
    env = {
        "PUBLISH_TO_APPGALLERY_ARTIFACT_PATH": str(artifact_path),
        "PUBLISH_TO_APPGALLERY_APP_ID": "123456",
        "PUBLISH_TO_APPGALLERY_CHINESE_MAINLAND_FLAG": "0",
        "PUBLISH_TO_APPGALLERY_DRY_RUN": "true",
    }
    env.update({f"PUBLISH_TO_APPGALLERY_{key}": value for key, value in overrides.items()})
    return env


def test_config_accepts_draft_without_credentials_or_production_wait(artifact_path: Path) -> None:
    config = load_config(
        [],
        _config_env(artifact_path, RELEASE_MODE="draft", PARSE_WAIT_SECONDS="0"),
    )

    assert config.release_mode is ReleaseMode.DRAFT
    assert config.parse_wait_seconds == 0


def test_config_normalizes_official_huawei_domain(artifact_path: Path) -> None:
    config = load_config([], _config_env(artifact_path, DOMAIN=f"{DEFAULT_DOMAIN}/"))

    assert config.domain == DEFAULT_DOMAIN


@pytest.mark.parametrize(
    "host",
    [
        "connect-api.cloud.huawei.com",
        "connect-api-dra.cloud.huawei.com",
        "connect-api-dre.cloud.huawei.com",
        "connect-api-drru.cloud.huawei.com",
    ],
)
def test_config_accepts_official_huawei_regions(artifact_path: Path, host: str) -> None:
    config = load_config([], _config_env(artifact_path, DOMAIN=f"https://{host}/api"))

    assert config.domain == f"https://{host}/api"


@pytest.mark.parametrize(
    ("override", "message"),
    [
        ({"DRY_RUN": "yes"}, "dry-run must be 'true' or 'false'"),
        ({"APP_ID": "a" * 33}, "app-id must be at most 32 characters"),
        ({"CHINESE_MAINLAND_FLAG": "2"}, "chinese-mainland-flag must be 0 or 1"),
        ({"RELEASE_REMARK": "short"}, "release-remark must be between 10 and 300"),
        ({"RELEASE_REMARK": "a" * 301}, "release-remark must be between 10 and 300"),
        ({"PARSE_WAIT_SECONDS": "119"}, "parse-wait-seconds must be at least 120"),
        ({"PARSE_WAIT_SECONDS": "soon"}, "parse-wait-seconds must be an integer"),
        ({"AUTH_MODE": "password"}, "auth-mode must be 'service-account' or 'api-client'"),
        ({"RELEASE_MODE": "testing"}, "release-mode must be 'draft' or 'production'"),
        ({"DOMAIN": "http://connect-api.cloud.huawei.com/api"}, "official Huawei API endpoint"),
        ({"DOMAIN": "https://example.com/api"}, "official Huawei API endpoint"),
        (
            {"DOMAIN": "https://user@connect-api.cloud.huawei.com/api"},
            "official Huawei API endpoint",
        ),
        (
            {"DOMAIN": "https://connect-api.cloud.huawei.com:443/api"},
            "official Huawei API endpoint",
        ),
        (
            {"DOMAIN": "https://connect-api.cloud.huawei.com/api?region=china"},
            "official Huawei API endpoint",
        ),
        (
            {"DOMAIN": "https://connect-api.cloud.huawei.com/api#fragment"},
            "official Huawei API endpoint",
        ),
    ],
)
def test_config_rejects_invalid_values(
    artifact_path: Path,
    override: dict[str, str],
    message: str,
) -> None:
    with pytest.raises(ValueError, match=message):
        load_config([], _config_env(artifact_path, **override))


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
    assert "artifact-file-name<<" in outputs
    assert "\napp-release.aab\n" in outputs
    assert "artifact-sha256<<" in outputs
    assert "\ncom.example.app\n" in outputs
    assert "\n42\n" in outputs
    assert "\ntrue\n" in outputs
    assert "\nfalse\n" in outputs


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
    assert summary["releaseMode"] == "production"
    assert summary["submitted"] is False


def test_dry_run_does_not_use_auth_transport_or_sleeper(artifact_path: Path) -> None:
    config = make_config(
        artifact_path,
        dry_run=True,
        service_account_json="not-json",
    )

    def unexpected_transport(_request):  # type: ignore[no-untyped-def]
        raise AssertionError("dry-run used transport")

    def unexpected_sleep(_seconds: float) -> None:
        raise AssertionError("dry-run slept")

    summary = publish(
        config,
        command_runner=metadata_runner(),
        transport=unexpected_transport,
        sleeper=unexpected_sleep,
    )

    assert summary["dryRun"] is True
    assert summary["submitted"] is False
