from __future__ import annotations

from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[2]
ACTION = ROOT / "publish-to-appgallery"


def test_action_metadata_exposes_public_contract() -> None:
    metadata = yaml.safe_load((ACTION / "action.yml").read_text(encoding="utf-8"))

    assert metadata["name"] == "Publish to Huawei AppGallery"
    assert metadata["author"] == "Irazu Labs"
    assert metadata["branding"] == {"icon": "upload-cloud", "color": "orange"}
    assert metadata["runs"]["using"] == "composite"
    assert "eas-build-id" not in metadata["inputs"]

    for input_name in [
        "artifact-path",
        "app-id",
        "chinese-mainland-flag",
        "auth-mode",
        "service-account-json",
        "client-id",
        "client-secret",
        "domain",
        "dry-run",
        "expected-package",
        "min-version-code",
        "max-aab-size-mb",
        "bundletool-jar",
        "parse-wait-seconds",
        "release-remark",
    ]:
        assert input_name in metadata["inputs"]

    for output_name in [
        "artifact-file-name",
        "artifact-path",
        "artifact-sha256",
        "artifact-size-bytes",
        "package-name",
        "version-code",
        "dry-run",
        "object-id",
        "submitted",
    ]:
        assert output_name in metadata["outputs"]


def test_root_docs_index_publish_to_appgallery() -> None:
    index = (ROOT / "docs" / "action-index.md").read_text(encoding="utf-8")
    readme = (ROOT / "README.md").read_text(encoding="utf-8")

    assert "publish-to-appgallery" in index
    assert "irazulabs/actions/publish-to-appgallery@v1" in index
    assert "publish-to-appgallery" in readme
