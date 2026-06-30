from __future__ import annotations

import subprocess
from collections.abc import Sequence
from pathlib import Path

import pytest

from publish_to_appgallery.config import PublishConfig


@pytest.fixture
def artifact_path(tmp_path: Path) -> Path:
    path = tmp_path / "app-release.aab"
    path.write_bytes(b"fake-aab-content")
    return path


def make_config(artifact_path: Path, **overrides: object) -> PublishConfig:
    values: dict[str, object] = {
        "artifact_path": artifact_path,
        "app_id": "123456",
        "chinese_mainland_flag": "0",
        "auth_mode": overrides.pop("auth_mode", None),
        "service_account_json": None,
        "client_id": None,
        "client_secret": None,
        "domain": "https://connect-api.cloud.huawei.com/api",
        "dry_run": True,
        "expected_package": None,
        "min_version_code": None,
        "max_aab_size_bytes": 150 * 1024 * 1024,
        "bundletool_jar": None,
        "parse_wait_seconds": 0,
        "release_remark": None,
    }
    from publish_to_appgallery.auth import AuthMode

    if values["auth_mode"] is None:
        values["auth_mode"] = AuthMode.SERVICE_ACCOUNT
    values.update(overrides)
    return PublishConfig(**values)  # type: ignore[arg-type]


def metadata_runner(package_name: str = "com.example.app", version_code: int = 42):
    def run(args: Sequence[str]) -> subprocess.CompletedProcess[str]:
        stdout = str(version_code) if "/manifest/@android:versionCode" in args else package_name
        return subprocess.CompletedProcess(args=list(args), returncode=0, stdout=stdout, stderr="")

    return run
