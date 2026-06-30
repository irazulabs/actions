from __future__ import annotations

import json
from pathlib import Path

import pytest

from publish_to_appgallery.auth import AuthMode
from publish_to_appgallery.cli import publish
from publish_to_appgallery.client import HttpRequest, HttpResponse, HuaweiApiError

from .conftest import make_config, metadata_runner
from .test_auth import service_account_json


class FakeTransport:
    def __init__(self) -> None:
        self.calls: list[HttpRequest] = []

    def __call__(self, request: HttpRequest) -> HttpResponse:
        self.calls.append(request)
        if "/publish/v2/upload-url/for-obs" in request.url:
            return json_response(
                {
                    "ret": {"code": 0, "msg": "success"},
                    "urlInfo": {
                        "objectId": "uploaded-object-id.aab",
                        "url": "https://upload.example/uploaded-object-id.aab",
                        "method": "PUT",
                        "headers": {"Content-Type": "application/octet-stream"},
                    },
                }
            )
        if request.url == "https://upload.example/uploaded-object-id.aab":
            return json_response({})
        if "/publish/v2/app-file-info" in request.url:
            return json_response({"ret": {"code": 0, "msg": "success"}})
        if "/publish/v2/app-submit" in request.url:
            return json_response({"ret": {"code": 0, "msg": "success"}})
        raise AssertionError(f"unexpected request: {request.url}")


def json_response(body: object, status: int = 200, reason: str = "OK") -> HttpResponse:
    return HttpResponse(
        status=status,
        reason=reason,
        body=json.dumps(body).encode("utf-8"),
        headers={},
    )


def test_huawei_api_sequence_uploads_updates_waits_and_submits(artifact_path: Path) -> None:
    transport = FakeTransport()
    waits: list[float] = []
    config = make_config(
        artifact_path,
        dry_run=False,
        service_account_json=service_account_json(),
        release_remark="Automated release",
    )

    summary = publish(
        config,
        command_runner=metadata_runner(),
        transport=transport,
        sleeper=waits.append,
    )

    assert summary["submitted"] is True
    assert waits == [0.0]
    assert [call.method for call in transport.calls] == ["GET", "PUT", "PUT", "POST"]
    assert "/upload-url/for-obs" in transport.calls[0].url
    assert transport.calls[1].url == "https://upload.example/uploaded-object-id.aab"
    assert "/app-file-info" in transport.calls[2].url
    assert "/app-submit" in transport.calls[3].url


def test_api_client_auth_obtains_token_and_sends_client_id(artifact_path: Path) -> None:
    calls: list[HttpRequest] = []

    def transport(request: HttpRequest) -> HttpResponse:
        calls.append(request)
        if "/oauth2/v1/token" in request.url:
            assert request.method == "POST"
            assert json.loads((request.body or b"{}").decode("utf-8")) == {
                "client_id": "client-id",
                "client_secret": "client-secret",
                "grant_type": "client_credentials",
            }
            return json_response({"access_token": "api-client-token"})
        return FakeTransport()(request)

    config = make_config(
        artifact_path,
        auth_mode=AuthMode.API_CLIENT,
        client_id="client-id",
        client_secret="client-secret",
        dry_run=False,
    )

    publish(config, command_runner=metadata_runner(), transport=transport, sleeper=lambda _: None)

    assert calls[0].url.endswith("/oauth2/v1/token")
    assert any(call.headers.get("client_id") == "client-id" for call in calls)
    assert any(call.headers.get("Authorization") == "Bearer api-client-token" for call in calls)


def test_huawei_ret_code_failure_is_reported(artifact_path: Path) -> None:
    def transport(_request: HttpRequest) -> HttpResponse:
        return json_response({"ret": {"code": 1, "msg": "not allowed"}})

    config = make_config(
        artifact_path,
        dry_run=False,
        service_account_json=service_account_json(),
    )

    with pytest.raises(HuaweiApiError, match="not allowed"):
        publish(
            config, command_runner=metadata_runner(), transport=transport, sleeper=lambda _: None
        )


def test_http_error_is_reported(artifact_path: Path) -> None:
    def transport(_request: HttpRequest) -> HttpResponse:
        return json_response({"error": "bad"}, status=500, reason="Server Error")

    config = make_config(
        artifact_path,
        dry_run=False,
        service_account_json=service_account_json(),
    )

    with pytest.raises(HuaweiApiError, match="500 Server Error"):
        publish(
            config, command_runner=metadata_runner(), transport=transport, sleeper=lambda _: None
        )


def test_non_json_response_is_reported(artifact_path: Path) -> None:
    def transport(_request: HttpRequest) -> HttpResponse:
        return HttpResponse(status=200, reason="OK", body=b"not json", headers={})

    config = make_config(
        artifact_path,
        dry_run=False,
        service_account_json=service_account_json(),
    )

    with pytest.raises(HuaweiApiError, match="non-JSON"):
        publish(
            config, command_runner=metadata_runner(), transport=transport, sleeper=lambda _: None
        )
