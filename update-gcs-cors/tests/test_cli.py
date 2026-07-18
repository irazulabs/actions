from __future__ import annotations

import hashlib
import json
import os
import subprocess
from pathlib import Path

import pytest

from update_gcs_cors.cli import (
    Config,
    load_config,
    normalize_bucket,
    update_cors,
    validate_cors_file,
)

from .conftest import write_cors


def test_load_config_normalizes_bucket_and_resolves_workspace_path(tmp_path: Path) -> None:
    cors_file = write_cors(tmp_path / "cors.json")

    config = load_config(
        [],
        {
            "GITHUB_WORKSPACE": str(tmp_path),
            "UPDATE_GCS_CORS_BUCKET": "gs://example-project.firebasestorage.app",
            "UPDATE_GCS_CORS_FILE": cors_file.name,
            "UPDATE_GCS_CORS_DRY_RUN": "true",
        },
    )

    assert config == Config(
        bucket="example-project.firebasestorage.app",
        cors_file=cors_file,
        dry_run=True,
    )


@pytest.mark.parametrize(
    "value",
    [
        "GS://bucket-name",
        "gs://bucket-name/object",
        "https://bucket-name",
        " bucket-name",
        "bucket name",
        "Bucket-name",
        "192.168.5.4",
        "goog-example",
        "ab",
        f"a{'b' * 63}",
        "bucket..name",
    ],
)
def test_invalid_bucket_names_are_rejected(value: str) -> None:
    with pytest.raises(ValueError, match="bucket"):
        normalize_bucket(value)


def test_valid_bucket_names_are_accepted() -> None:
    assert normalize_bucket("bucket_name-123") == "bucket_name-123"
    assert normalize_bucket("gs://example-project.firebasestorage.app") == (
        "example-project.firebasestorage.app"
    )


def test_cors_file_is_validated_and_hashed(tmp_path: Path) -> None:
    cors_file = write_cors(tmp_path / "cors.json")

    policy = validate_cors_file(cors_file)

    assert policy.rule_count == 1
    assert policy.path == cors_file
    assert policy.sha256 == hashlib.sha256(cors_file.read_bytes()).hexdigest()


def test_empty_list_is_an_explicit_clear_policy(tmp_path: Path) -> None:
    cors_file = write_cors(tmp_path / "cors.json", [])

    summary = update_cors(
        Config("bucket-name", cors_file, True),
        command_runner=lambda *_: pytest.fail("dry-run invoked gcloud"),
    )

    assert summary["operation"] == "clear"
    assert summary["rule-count"] == 0


@pytest.mark.parametrize(
    ("document", "message"),
    [
        ({"cors": []}, "without a top-level 'cors' wrapper"),
        (["rule"], "rule 0 must be an object"),
        ([{"origin": ["*"], "method": ["GET"], "typo": []}], "unsupported fields"),
        ([{"origin": [], "method": ["GET"]}], "origin must be a non-empty list"),
        ([{"origin": ["*"], "method": []}], "method must be a non-empty list"),
        ([{"origin": [1], "method": ["GET"]}], "origin must contain"),
        ([{"origin": ["*"], "method": ["GET"], "responseHeader": "x"}], "responseHeader"),
        ([{"origin": ["*"], "method": ["GET"], "maxAgeSeconds": True}], "maxAgeSeconds"),
        ([{"origin": ["*"], "method": ["GET"], "maxAgeSeconds": -1}], "maxAgeSeconds"),
    ],
)
def test_invalid_cors_documents_are_rejected(
    tmp_path: Path,
    document: object,
    message: str,
) -> None:
    cors_file = write_cors(tmp_path / "cors.json", document)

    with pytest.raises(ValueError, match=message):
        validate_cors_file(cors_file)


def test_invalid_json_and_utf8_are_rejected(tmp_path: Path) -> None:
    malformed = tmp_path / "malformed.json"
    malformed.write_text("[", encoding="utf-8")
    invalid_utf8 = tmp_path / "invalid.json"
    invalid_utf8.write_bytes(b"\xff")

    with pytest.raises(ValueError, match="valid JSON"):
        validate_cors_file(malformed)
    with pytest.raises(ValueError, match="valid UTF-8"):
        validate_cors_file(invalid_utf8)


def test_update_invokes_exact_gcloud_command_and_preserves_environment(tmp_path: Path) -> None:
    cors_file = write_cors(tmp_path / "cors file.json")
    calls: list[tuple[list[str], dict[str, str], int]] = []

    def run(command: object, env: object, timeout: int) -> None:
        calls.append((list(command), dict(env), timeout))  # type: ignore[arg-type]

    summary = update_cors(
        Config("bucket-name", cors_file, False),
        command_runner=run,
        env={"GOOGLE_APPLICATION_CREDENTIALS": "/tmp/credentials.json"},
    )

    assert calls == [
        (
            [
                "gcloud",
                "storage",
                "buckets",
                "update",
                "gs://bucket-name",
                f"--cors-file={cors_file}",
                "--quiet",
            ],
            {
                "GOOGLE_APPLICATION_CREDENTIALS": "/tmp/credentials.json",
                "CLOUDSDK_CORE_DISABLE_PROMPTS": "1",
            },
            120,
        )
    ]
    assert summary["operation"] == "replace"


def test_outputs_are_written_only_after_success(tmp_path: Path) -> None:
    cors_file = write_cors(tmp_path / "cors.json")
    output = tmp_path / "output.txt"

    def fail(*_: object) -> None:
        raise subprocess.CalledProcessError(1, ["gcloud"])

    with pytest.raises(subprocess.CalledProcessError):
        update_cors(
            Config("bucket-name", cors_file, False), command_runner=fail, output_path=output
        )
    assert not output.exists()

    summary = update_cors(Config("bucket-name", cors_file, True), output_path=output)
    content = output.read_text(encoding="utf-8")
    for name in ["bucket", "cors-file", "cors-sha256", "rule-count", "dry-run"]:
        assert f"{name}<<github_output_" in content
    assert summary["dry-run"] == "true"


def test_cli_dry_run_prints_summary(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    cors_file = write_cors(tmp_path / "cors.json")
    from update_gcs_cors.cli import main

    exit_code = main(
        [
            "--bucket",
            "bucket-name",
            "--cors-file",
            str(cors_file),
            "--dry-run",
        ]
    )

    summary = json.loads(capsys.readouterr().out)
    assert exit_code == 0
    assert summary["bucket"] == "bucket-name"
    assert summary["dry-run"] == "true"


def test_validate_only_performs_local_preflight(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    cors_file = write_cors(tmp_path / "cors.json")
    from update_gcs_cors.cli import main

    exit_code = main(
        [
            "--bucket",
            "bucket-name",
            "--cors-file",
            str(cors_file),
            "--validate-only",
        ]
    )

    summary = json.loads(capsys.readouterr().out)
    assert exit_code == 0
    assert summary["validated"] is True
    assert summary["rule-count"] == 1


def test_dry_run_environment_value_is_strict(tmp_path: Path) -> None:
    cors_file = write_cors(tmp_path / "cors.json")
    with pytest.raises(ValueError, match="dry-run"):
        load_config(
            [],
            {
                "UPDATE_GCS_CORS_BUCKET": "bucket-name",
                "UPDATE_GCS_CORS_FILE": str(cors_file),
                "UPDATE_GCS_CORS_DRY_RUN": "TRUE",
            },
        )


def test_command_timeout_is_reported_by_cli(tmp_path: Path, monkeypatch, capsys) -> None:  # type: ignore[no-untyped-def]
    cors_file = write_cors(tmp_path / "cors.json")
    monkeypatch.setenv("UPDATE_GCS_CORS_BUCKET", "bucket-name")
    monkeypatch.setenv("UPDATE_GCS_CORS_FILE", str(cors_file))
    monkeypatch.setenv("UPDATE_GCS_CORS_DRY_RUN", "false")
    monkeypatch.delenv("GITHUB_OUTPUT", raising=False)

    def timeout(*_: object, **__: object) -> None:
        raise subprocess.TimeoutExpired(["gcloud"], 120)

    monkeypatch.setattr(subprocess, "run", timeout)
    from update_gcs_cors.cli import main

    assert main([]) == 1
    assert "timed out" in capsys.readouterr().err


def test_no_generated_credentials_are_required(tmp_path: Path) -> None:
    cors_file = write_cors(tmp_path / "cors.json")
    old_credentials = os.environ.pop("GOOGLE_APPLICATION_CREDENTIALS", None)
    try:
        summary = update_cors(Config("bucket-name", cors_file, True))
    finally:
        if old_credentials is not None:
            os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = old_credentials
    assert summary["dry-run"] == "true"
