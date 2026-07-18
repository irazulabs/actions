from __future__ import annotations

import tomllib
from pathlib import Path

import yaml

from publish_to_appgallery import __version__

ROOT = Path(__file__).resolve().parents[2]
ACTION = ROOT / "publish-to-appgallery"


def test_action_metadata_exposes_public_contract() -> None:
    metadata = yaml.safe_load((ACTION / "action.yml").read_text(encoding="utf-8"))

    assert metadata["name"] == "Publish to Huawei AppGallery"
    assert metadata["author"] == "Irazu Labs"
    assert metadata["branding"] == {"icon": "upload-cloud", "color": "orange"}
    assert metadata["runs"]["using"] == "composite"
    assert "eas-build-id" not in metadata["inputs"]

    input_names = [
        "artifact-path",
        "app-id",
        "chinese-mainland-flag",
        "auth-mode",
        "service-account-json",
        "client-id",
        "client-secret",
        "domain",
        "dry-run",
        "release-mode",
        "expected-package",
        "min-version-code",
        "max-aab-size-mb",
        "bundletool-jar",
        "parse-wait-seconds",
        "release-remark",
    ]
    assert set(metadata["inputs"]) == set(input_names)
    assert {name for name, value in metadata["inputs"].items() if value.get("required")} == {
        "artifact-path",
        "app-id",
        "chinese-mainland-flag",
    }
    assert {
        name: metadata["inputs"][name]["default"]
        for name in [
            "auth-mode",
            "domain",
            "dry-run",
            "release-mode",
            "max-aab-size-mb",
            "parse-wait-seconds",
        ]
    } == {
        "auth-mode": "service-account",
        "domain": "https://connect-api.cloud.huawei.com/api",
        "dry-run": "false",
        "release-mode": "production",
        "max-aab-size-mb": "150",
        "parse-wait-seconds": "120",
    }

    output_names = [
        "artifact-file-name",
        "artifact-path",
        "artifact-sha256",
        "artifact-size-bytes",
        "package-name",
        "version-code",
        "dry-run",
        "object-id",
        "submitted",
    ]
    assert set(metadata["outputs"]) == set(output_names)
    assert {name: value["value"] for name, value in metadata["outputs"].items()} == {
        name: f"${{{{ steps.publish.outputs.{name} }}}}" for name in output_names
    }

    steps = metadata["runs"]["steps"]
    assert steps[0]["uses"] == ("actions/setup-python@a26af69be951a213d495a4c3e4e4022e16d87065")
    assert steps[0]["with"]["python-version"] == "3.11"
    assert steps[1]["run"] == 'python -m pip install "${GITHUB_ACTION_PATH}"'
    assert steps[2]["id"] == "publish"
    assert steps[2]["run"] == "python -m publish_to_appgallery"
    assert steps[2]["env"] == {
        f"PUBLISH_TO_APPGALLERY_{name.replace('-', '_').upper()}": f"${{{{ inputs.{name} }}}}"
        for name in input_names
    }


def test_python_package_matches_action_runtime() -> None:
    package = tomllib.loads((ACTION / "pyproject.toml").read_text(encoding="utf-8"))

    assert package["project"]["version"] == __version__ == "1.1.0"
    assert package["project"]["requires-python"] == ">=3.11"
    assert package["project"]["scripts"]["publish-to-appgallery"] == (
        "publish_to_appgallery.cli:main"
    )


def test_root_docs_index_publish_to_appgallery() -> None:
    index = (ROOT / "docs" / "action-index.md").read_text(encoding="utf-8")
    readme = (ROOT / "README.md").read_text(encoding="utf-8")

    assert "publish-to-appgallery" in index
    assert "irazulabs/actions/publish-to-appgallery@" in index
    assert "publish-to-appgallery" in readme
