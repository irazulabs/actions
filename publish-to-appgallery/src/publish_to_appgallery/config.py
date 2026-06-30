from __future__ import annotations

import argparse
import os
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path

from publish_to_appgallery.auth import AuthMode

DEFAULT_DOMAIN = "https://connect-api.cloud.huawei.com/api"
DEFAULT_MAX_AAB_SIZE_MB = 150
DEFAULT_PARSE_WAIT_SECONDS = 120
ENV_PREFIX = "PUBLISH_TO_APPGALLERY_"


@dataclass(frozen=True)
class PublishConfig:
    artifact_path: Path
    app_id: str
    chinese_mainland_flag: str
    auth_mode: AuthMode
    service_account_json: str | None
    client_id: str | None
    client_secret: str | None
    domain: str
    dry_run: bool
    expected_package: str | None
    min_version_code: int | None
    max_aab_size_bytes: int
    bundletool_jar: Path | None
    parse_wait_seconds: int
    release_remark: str | None


def _optional_string(value: str | None) -> str | None:
    if value is None:
        return None
    stripped = value.strip()
    return stripped or None


def _required_string(value: str | None, name: str) -> str:
    stripped = _optional_string(value)
    if stripped is None:
        raise ValueError(f"{name} is required")
    return stripped


def _parse_bool(value: str | bool | None) -> bool:
    if isinstance(value, bool):
        return value
    if value is None or value.strip() == "":
        return False
    return value.strip().lower() in {"1", "true", "yes", "on"}


def _parse_non_negative_int(value: str | None, name: str) -> int | None:
    stripped = _optional_string(value)
    if stripped is None:
        return None
    parsed = int(stripped)
    if parsed < 0:
        raise ValueError(f"{name} must be a non-negative integer")
    return parsed


def _parse_positive_int(value: str | None, name: str, default: int) -> int:
    parsed = _parse_non_negative_int(value, name)
    if parsed is None:
        return default
    if parsed <= 0:
        raise ValueError(f"{name} must be greater than zero")
    return parsed


def _env(env: Mapping[str, str], name: str) -> str | None:
    return env.get(f"{ENV_PREFIX}{name}")


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Publish an AAB to Huawei AppGallery.")
    parser.add_argument("--artifact-path")
    parser.add_argument("--app-id")
    parser.add_argument("--chinese-mainland-flag")
    parser.add_argument("--auth-mode")
    parser.add_argument("--service-account-json")
    parser.add_argument("--client-id")
    parser.add_argument("--client-secret")
    parser.add_argument("--domain")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--expected-package")
    parser.add_argument("--min-version-code")
    parser.add_argument("--max-aab-size-mb")
    parser.add_argument("--bundletool-jar")
    parser.add_argument("--parse-wait-seconds")
    parser.add_argument("--release-remark")
    return parser


def load_config(
    argv: Sequence[str] | None = None,
    env: Mapping[str, str] | None = None,
) -> PublishConfig:
    env_values = env if env is not None else os.environ
    args = _build_parser().parse_args(argv)

    artifact_path = _required_string(
        args.artifact_path or _env(env_values, "ARTIFACT_PATH"),
        "artifact-path",
    )
    app_id = _required_string(args.app_id or _env(env_values, "APP_ID"), "app-id")
    chinese_mainland_flag = _required_string(
        args.chinese_mainland_flag or _env(env_values, "CHINESE_MAINLAND_FLAG"),
        "chinese-mainland-flag",
    )

    auth_mode_value = _optional_string(args.auth_mode or _env(env_values, "AUTH_MODE"))
    auth_mode = AuthMode(auth_mode_value or AuthMode.SERVICE_ACCOUNT.value)
    dry_run = bool(args.dry_run or _parse_bool(_env(env_values, "DRY_RUN")))
    service_account_json = _optional_string(
        args.service_account_json or _env(env_values, "SERVICE_ACCOUNT_JSON")
    )
    client_id = _optional_string(args.client_id or _env(env_values, "CLIENT_ID"))
    client_secret = _optional_string(args.client_secret or _env(env_values, "CLIENT_SECRET"))

    if not dry_run and auth_mode is AuthMode.SERVICE_ACCOUNT and service_account_json is None:
        raise ValueError("service-account-json is required for service-account auth mode")
    if not dry_run and auth_mode is AuthMode.API_CLIENT:
        _required_string(client_id, "client-id")
        _required_string(client_secret, "client-secret")

    max_aab_size_mb = _parse_positive_int(
        args.max_aab_size_mb or _env(env_values, "MAX_AAB_SIZE_MB"),
        "max-aab-size-mb",
        DEFAULT_MAX_AAB_SIZE_MB,
    )
    parse_wait_seconds = _parse_non_negative_int(
        args.parse_wait_seconds or _env(env_values, "PARSE_WAIT_SECONDS"),
        "parse-wait-seconds",
    )

    bundletool_jar = _optional_string(args.bundletool_jar or _env(env_values, "BUNDLETOOL_JAR"))

    return PublishConfig(
        artifact_path=Path(artifact_path),
        app_id=app_id,
        chinese_mainland_flag=chinese_mainland_flag,
        auth_mode=auth_mode,
        service_account_json=service_account_json,
        client_id=client_id,
        client_secret=client_secret,
        domain=_optional_string(args.domain or _env(env_values, "DOMAIN")) or DEFAULT_DOMAIN,
        dry_run=dry_run,
        expected_package=_optional_string(
            args.expected_package or _env(env_values, "EXPECTED_PACKAGE")
        ),
        min_version_code=_parse_non_negative_int(
            args.min_version_code or _env(env_values, "MIN_VERSION_CODE"),
            "min-version-code",
        ),
        max_aab_size_bytes=max_aab_size_mb * 1024 * 1024,
        bundletool_jar=Path(bundletool_jar) if bundletool_jar is not None else None,
        parse_wait_seconds=parse_wait_seconds
        if parse_wait_seconds is not None
        else DEFAULT_PARSE_WAIT_SECONDS,
        release_remark=_optional_string(args.release_remark or _env(env_values, "RELEASE_REMARK")),
    )
