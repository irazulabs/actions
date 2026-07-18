from __future__ import annotations

import subprocess
import tomllib
from pathlib import Path

import yaml

from update_gcs_cors import __version__

ROOT = Path(__file__).resolve().parents[2]
ACTION = ROOT / "update-gcs-cors"


def test_action_metadata_exposes_public_contract() -> None:
    metadata = yaml.safe_load((ACTION / "action.yml").read_text(encoding="utf-8"))

    assert metadata["name"] == "Update GCS CORS"
    assert metadata["author"] == "Irazu Labs"
    assert metadata["runs"]["using"] == "composite"
    assert set(metadata["inputs"]) == {"bucket", "cors-file", "dry-run"}
    assert metadata["inputs"]["bucket"]["required"] is True
    assert metadata["inputs"]["cors-file"]["required"] is True
    assert metadata["inputs"]["dry-run"]["default"] == "false"
    assert not any("auth" in name or "credential" in name for name in metadata["inputs"])

    outputs = {"bucket", "cors-file", "cors-sha256", "rule-count", "dry-run"}
    assert set(metadata["outputs"]) == outputs
    assert {name: value["value"] for name, value in metadata["outputs"].items()} == {
        name: f"${{{{ steps.update.outputs.{name} }}}}" for name in outputs
    }

    steps = metadata["runs"]["steps"]
    assert steps[0]["uses"] == "actions/setup-python@a26af69be951a213d495a4c3e4e4022e16d87065"
    assert steps[1]["run"] == 'python -m pip install "${GITHUB_ACTION_PATH}"'
    assert steps[2]["run"] == "python -m update_gcs_cors --validate-only"
    assert steps[3]["uses"] == (
        "google-github-actions/setup-gcloud@aa5489c8933f4cc7a4f7d45035b3b1440c9c10db"
    )
    assert steps[3]["if"] == "inputs['dry-run'] != 'true'"
    assert steps[3]["with"]["version"] == "576.0.0"
    assert steps[4]["run"] == "python -m update_gcs_cors"
    assert steps[4]["env"] == {
        "UPDATE_GCS_CORS_BUCKET": "${{ inputs.bucket }}",
        "UPDATE_GCS_CORS_FILE": "${{ inputs.cors-file }}",
        "UPDATE_GCS_CORS_DRY_RUN": "${{ inputs.dry-run }}",
    }


def test_python_package_matches_action_runtime() -> None:
    package = tomllib.loads((ACTION / "pyproject.toml").read_text(encoding="utf-8"))
    assert package["project"]["version"] == __version__ == "1.1.0"
    assert package["project"]["dependencies"] == []
    assert package["project"]["requires-python"] == ">=3.11"
    assert package["project"]["scripts"]["update-gcs-cors"] == "update_gcs_cors.cli:main"


def test_action_contains_no_generated_or_vendored_code() -> None:
    forbidden = {"build", "dist", "node_modules", "vendor", "__pycache__"}
    tracked = subprocess.run(
        ["git", "ls-files", str(ACTION.relative_to(ROOT))],
        check=True,
        capture_output=True,
        text=True,
    ).stdout.splitlines()
    assert not [path for path in tracked if forbidden.intersection(Path(path).parts)]
    assert not [path for path in tracked if path.endswith(".whl")]


def test_root_docs_index_update_gcs_cors() -> None:
    index = (ROOT / "docs" / "action-index.md").read_text(encoding="utf-8")
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    assert "update-gcs-cors" in index
    assert "irazulabs/actions/update-gcs-cors@" in index
    assert "update-gcs-cors" in readme
