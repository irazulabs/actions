from __future__ import annotations

import uuid
from pathlib import Path

from publish_to_appgallery import outputs
from publish_to_appgallery.artifact import ArtifactInfo, BundleMetadata
from publish_to_appgallery.client import PublishResult

from .conftest import make_config


def test_outputs_use_collision_safe_multiline_records(tmp_path: Path, monkeypatch) -> None:  # type: ignore[no-untyped-def]
    colliding = f"github_output_{uuid.UUID(int=1).hex}"
    delimiter = f"github_output_{uuid.UUID(int=2).hex}"
    generated = iter((uuid.UUID(int=1), uuid.UUID(int=2)))
    monkeypatch.setattr(outputs.uuid, "uuid4", lambda: next(generated))
    output_path = tmp_path / "github-output.txt"
    output_path.write_bytes(b"existing=value\n")
    artifact = ArtifactInfo(
        path=Path("build/app%release.aab"),
        file_name=f"app%release.aab\r\n{colliding}\nsubmitted=true",
        size_bytes=0,
        sha256="abc%25\rsha",
        metadata=BundleMetadata(package_name=None, version_code=None),
    )
    config = make_config(artifact.path)
    result = PublishResult(object_id="object%id\r\ninjected=value", submitted=False)

    outputs.write_github_outputs(output_path, artifact, config, result)

    values = outputs.output_values(artifact, config, result)
    expected_records = "".join(
        f"{name}<<{delimiter}\n{'' if value is None else value}\n{delimiter}\n"
        for name, value in values.items()
    )
    assert output_path.read_bytes() == f"existing=value\n{expected_records}".encode()


def test_outputs_are_a_noop_without_output_path(tmp_path: Path) -> None:
    artifact = ArtifactInfo(
        path=tmp_path / "app.aab",
        file_name="app.aab",
        size_bytes=0,
        sha256="abc",
        metadata=BundleMetadata(),
    )

    outputs.write_github_outputs(
        None,
        artifact,
        make_config(artifact.path),
        PublishResult(object_id=None, submitted=False),
    )

    assert list(tmp_path.iterdir()) == []
