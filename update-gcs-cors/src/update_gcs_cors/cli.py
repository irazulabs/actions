from __future__ import annotations

import argparse
import hashlib
import ipaddress
import json
import os
import re
import subprocess
import sys
import uuid
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

ENV_PREFIX = "UPDATE_GCS_CORS_"
COMMAND_TIMEOUT_SECONDS = 120
BUCKET_PATTERN = re.compile(r"^[a-z0-9][a-z0-9._-]*[a-z0-9]$")
CORS_KEYS = {"origin", "method", "responseHeader", "maxAgeSeconds"}

CommandRunner = Callable[[Sequence[str], Mapping[str, str], int], None]


@dataclass(frozen=True)
class Config:
    bucket: str
    cors_file: Path
    dry_run: bool
    validate_only: bool = False


@dataclass(frozen=True)
class CorsPolicy:
    path: Path
    sha256: str
    rule_count: int


def _required(value: str | None, name: str) -> str:
    if value is None or not value:
        raise ValueError(f"{name} is required")
    return value


def _parse_bool(value: str | None) -> bool:
    if value == "true":
        return True
    if value == "false":
        return False
    raise ValueError("dry-run must be 'true' or 'false'")


def normalize_bucket(value: str) -> str:
    if value != value.strip() or any(character.isspace() for character in value):
        raise ValueError("bucket must not contain whitespace")
    bucket = value.removeprefix("gs://")
    if "://" in bucket or any(character in bucket for character in "/?#"):
        raise ValueError("bucket must be a bucket name or gs:// bucket URL without an object path")
    max_length = 222 if "." in bucket else 63
    components = bucket.split(".")
    if (
        not 3 <= len(bucket) <= max_length
        or not BUCKET_PATTERN.fullmatch(bucket)
        or any(not component or len(component) > 63 for component in components)
    ):
        raise ValueError("bucket does not satisfy Google Cloud Storage naming requirements")
    try:
        ipaddress.ip_address(bucket)
    except ValueError:
        pass
    else:
        raise ValueError("bucket must not be an IP address")
    if bucket.startswith("goog"):
        raise ValueError("bucket must not begin with 'goog'")
    return bucket


def _resolve_cors_file(value: str, env: Mapping[str, str]) -> Path:
    path = Path(value)
    if not path.is_absolute():
        path = Path(env.get("GITHUB_WORKSPACE", Path.cwd())) / path
    path = path.resolve()
    if not path.is_file():
        raise ValueError("cors-file must be an existing regular file")
    return path


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Update Google Cloud Storage bucket CORS.")
    parser.add_argument("--bucket")
    parser.add_argument("--cors-file")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--validate-only", action="store_true", help=argparse.SUPPRESS)
    return parser


def load_config(
    argv: Sequence[str] | None = None,
    env: Mapping[str, str] | None = None,
) -> Config:
    values = env if env is not None else os.environ
    args = _build_parser().parse_args(argv)
    bucket_value = args.bucket if args.bucket is not None else values.get(f"{ENV_PREFIX}BUCKET")
    file_value = args.cors_file if args.cors_file is not None else values.get(f"{ENV_PREFIX}FILE")
    dry_run = args.dry_run or _parse_bool(values.get(f"{ENV_PREFIX}DRY_RUN", "false"))
    return Config(
        bucket=normalize_bucket(_required(bucket_value, "bucket")),
        cors_file=_resolve_cors_file(_required(file_value, "cors-file"), values),
        dry_run=dry_run,
        validate_only=args.validate_only,
    )


def _validate_string_list(value: Any, name: str, *, required: bool) -> None:
    if not isinstance(value, list) or (required and not value):
        qualifier = "non-empty " if required else ""
        raise ValueError(f"{name} must be a {qualifier}list of non-empty strings")
    if any(not isinstance(item, str) or not item for item in value):
        raise ValueError(f"{name} must contain only non-empty strings")


def validate_cors_file(path: Path) -> CorsPolicy:
    raw = path.read_bytes()
    try:
        document = json.loads(raw.decode("utf-8"))
    except UnicodeDecodeError:
        raise ValueError("cors-file must be valid UTF-8") from None
    except json.JSONDecodeError as exc:
        raise ValueError(f"cors-file must contain valid JSON: {exc.msg}") from None
    if not isinstance(document, list):
        raise ValueError("cors-file must contain a JSON list without a top-level 'cors' wrapper")
    for index, rule in enumerate(document):
        if not isinstance(rule, dict):
            raise ValueError(f"CORS rule {index} must be an object")
        unknown = set(rule) - CORS_KEYS
        if unknown:
            raise ValueError(
                f"CORS rule {index} contains unsupported fields: {', '.join(sorted(unknown))}"
            )
        _validate_string_list(rule.get("origin"), f"CORS rule {index} origin", required=True)
        _validate_string_list(rule.get("method"), f"CORS rule {index} method", required=True)
        if "responseHeader" in rule:
            _validate_string_list(
                rule["responseHeader"],
                f"CORS rule {index} responseHeader",
                required=False,
            )
        if "maxAgeSeconds" in rule:
            max_age = rule["maxAgeSeconds"]
            if isinstance(max_age, bool) or not isinstance(max_age, int) or max_age < 0:
                raise ValueError(f"CORS rule {index} maxAgeSeconds must be a non-negative integer")
    return CorsPolicy(
        path=path,
        sha256=hashlib.sha256(raw).hexdigest(),
        rule_count=len(document),
    )


def _run_command(command: Sequence[str], env: Mapping[str, str], timeout: int) -> None:
    subprocess.run(list(command), check=True, env=dict(env), timeout=timeout)


def _write_outputs(output_path: Path | None, values: Mapping[str, object]) -> None:
    if output_path is None:
        return
    value_lines = {line for value in values.values() for line in str(value).splitlines()}
    delimiter = f"github_output_{uuid.uuid4().hex}"
    while delimiter in value_lines:
        delimiter = f"github_output_{uuid.uuid4().hex}"
    records = "".join(
        f"{name}<<{delimiter}\n{value}\n{delimiter}\n" for name, value in values.items()
    )
    with output_path.open("a", encoding="utf-8", newline="") as handle:
        handle.write(records)


def update_cors(
    config: Config,
    *,
    command_runner: CommandRunner = _run_command,
    env: Mapping[str, str] | None = None,
    output_path: Path | None = None,
) -> dict[str, object]:
    policy = validate_cors_file(config.cors_file)
    operation = "clear" if policy.rule_count == 0 else "replace"
    if not config.dry_run:
        command_env = dict(env if env is not None else os.environ)
        command_env["CLOUDSDK_CORE_DISABLE_PROMPTS"] = "1"
        command_runner(
            [
                "gcloud",
                "storage",
                "buckets",
                "update",
                f"gs://{config.bucket}",
                f"--cors-file={policy.path}",
                "--quiet",
            ],
            command_env,
            COMMAND_TIMEOUT_SECONDS,
        )
    values: dict[str, object] = {
        "bucket": config.bucket,
        "cors-file": policy.path,
        "cors-sha256": policy.sha256,
        "rule-count": policy.rule_count,
        "dry-run": str(config.dry_run).lower(),
    }
    _write_outputs(output_path, values)
    return {**values, "operation": operation}


def _github_output_path(env: Mapping[str, str]) -> Path | None:
    value = env.get("GITHUB_OUTPUT")
    return Path(value) if value else None


def main(argv: Sequence[str] | None = None) -> int:
    try:
        config = load_config(argv)
        summary = (
            {
                "bucket": config.bucket,
                "cors-file": config.cors_file,
                "rule-count": validate_cors_file(config.cors_file).rule_count,
                "validated": True,
            }
            if config.validate_only
            else update_cors(config, output_path=_github_output_path(os.environ))
        )
    except Exception as exc:  # noqa: BLE001 - CLI should turn all failures into readable output.
        print(str(exc), file=sys.stderr)
        return 1
    print(json.dumps(summary, indent=2, sort_keys=True, default=str))
    return 0
